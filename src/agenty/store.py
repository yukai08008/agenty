"""Persistent multi-agent control plane rooted at ``~/.agenty``."""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RUNTIME_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")
DEFAULT_RUNTIME_COMMANDS = {
    "codex": "codex",
    "opencode": "opencode",
    "claude": "claude",
}


class AgentyError(RuntimeError):
    """Base error for safe, user-facing Agenty failures."""


class NotFoundError(AgentyError):
    """Raised when an Agent or runtime profile cannot be found."""


class ConflictError(AgentyError):
    """Raised when an operation would overwrite or duplicate state."""


@dataclass(frozen=True)
class AgentRecord:
    """Resolved Agent identity plus its control-plane directory."""

    agent_id: str
    name: str
    runtime: str
    directory: Path
    metadata: dict[str, Any]
    bindings: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_agent_name(name: str) -> str:
    value = name.strip()
    if not AGENT_NAME_PATTERN.fullmatch(value):
        raise AgentyError(
            "Agent name must be 1-64 characters and use only letters, "
            "numbers, dots, underscores, or hyphens."
        )
    return value


def validate_runtime_name(name: str) -> str:
    value = name.strip()
    if not RUNTIME_NAME_PATTERN.fullmatch(value):
        raise AgentyError(
            "Runtime name must start with a letter and use only letters, "
            "numbers, dots, underscores, or hyphens."
        )
    return value


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NotFoundError(f"Missing state file: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AgentyError(f"Cannot read JSON file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AgentyError(f"JSON root must be an object: {path}")
    return value


def atomic_write_text(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        os.chmod(path, 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class AgentyStore:
    """Read and update Agenty's local multi-agent control plane."""

    def __init__(
        self,
        home: Path | str | None = None,
        agents_home: Path | str | None = None,
    ) -> None:
        configured_home = home or os.environ.get("AGENTY_HOME")
        configured_agents_home = agents_home or os.environ.get("AGENTY_AGENTS_HOME")
        self.home = (
            Path(configured_home).expanduser().resolve()
            if configured_home
            else Path.home() / ".agenty"
        )
        self.agents_home = (
            Path(configured_agents_home).expanduser().resolve()
            if configured_agents_home
            else Path.home() / "agents"
        )
        self.agents_dir = self.home / "agents"
        self.runtimes_dir = self.home / "runtimes"
        self.locks_dir = self.home / "locks"
        self.logs_dir = self.home / "logs"

    @property
    def initialized(self) -> bool:
        return (self.home / "config.toml").is_file() and self.agents_dir.is_dir()

    def initialize(self) -> list[dict[str, Any]]:
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.home, 0o700)
        for directory in (self.agents_dir, self.runtimes_dir, self.locks_dir, self.logs_dir):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(directory, 0o700)

        config_path = self.home / "config.toml"
        if not config_path.exists():
            atomic_write_text(
                config_path,
                "# Agenty control-plane configuration\n"
                "schema_version = 1\n"
                f'agents_home = "{self.agents_home}"\n',
            )

        detected = []
        for runtime_name, command in DEFAULT_RUNTIME_COMMANDS.items():
            executable = shutil.which(command)
            if executable:
                detected.append(self.add_runtime(runtime_name, [executable], overwrite=False))
        self.append_system_event("control_plane.initialized", {"home": str(self.home)})
        return detected

    def require_initialized(self) -> None:
        if not self.initialized:
            raise AgentyError(
                f"Agenty is not initialized. Run `agenty init` first. "
                f"Expected: {self.home}"
            )

    def add_runtime(
        self, name: str, argv: list[str], *, overwrite: bool = False
    ) -> dict[str, Any]:
        self.require_initialized()
        runtime_name = validate_runtime_name(name)
        if not argv or not all(isinstance(item, str) and item for item in argv):
            raise AgentyError("Runtime command must contain at least one non-empty argument.")
        self.runtimes_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.runtimes_dir / f"{runtime_name}.json"
        if path.exists() and not overwrite:
            return read_json(path)
        profile = {
            "schema_version": 1,
            "name": runtime_name,
            "argv": argv,
            "updated_at": utc_now(),
        }
        atomic_write_json(path, profile)
        return profile

    def get_runtime(self, name: str) -> dict[str, Any]:
        self.require_initialized()
        runtime_name = validate_runtime_name(name)
        path = self.runtimes_dir / f"{runtime_name}.json"
        if not path.is_file():
            raise NotFoundError(
                f"Runtime `{runtime_name}` is not registered. Use `agenty runtime add`."
            )
        return read_json(path)

    def list_runtimes(self) -> list[dict[str, Any]]:
        self.require_initialized()
        return [read_json(path) for path in sorted(self.runtimes_dir.glob("*.json"))]

    def claim(self, name: str, runtime: str) -> AgentRecord:
        self.require_initialized()
        agent_name = validate_agent_name(name)
        runtime_name = validate_runtime_name(runtime)
        self.get_runtime(runtime_name)

        with file_lock(self.locks_dir / "registry.lock"):
            for existing in self.list_agents():
                if existing.name.casefold() == agent_name.casefold():
                    raise ConflictError(f"Agent name already exists: {agent_name}")

            agent_id = f"agt_{uuid.uuid4().hex}"
            agent_dir = self.agents_dir / agent_id
            for relative in (
                "state/checkpoints",
                "runtime",
                "logs",
                "persistence",
                "scratch",
            ):
                directory = agent_dir / relative
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                os.chmod(directory, 0o700)

            metadata = {
                "schema_version": 1,
                "agent_id": agent_id,
                "name": agent_name,
                "runtime": runtime_name,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            }
            bindings = {
                "schema_version": 1,
                "active_root": None,
                "suite": None,
                "workspace": None,
                "project": None,
                "retained_source": None,
                "updated_at": utc_now(),
            }
            atomic_write_json(agent_dir / "metadata.json", metadata)
            atomic_write_json(agent_dir / "bindings.json", bindings)
            atomic_write_text(
                agent_dir / "scratch" / "AGENTS.md",
                f"# {agent_name}\n\n"
                "This is a claimed Agenty Agent without a dedicated Worker workspace.\n"
                "Use only the current task context and avoid treating this scratch "
                "directory as a project.\n",
            )

            from agenty.state import AgentStateMachine

            AgentStateMachine(agent_dir).bootstrap(agent_id)

        self.append_system_event("agent.claimed", {"agent_id": agent_id, "name": agent_name})
        return self.resolve_agent(agent_id)

    def list_agents(self) -> list[AgentRecord]:
        if not self.agents_dir.is_dir():
            return []
        records = []
        for directory in sorted(self.agents_dir.glob("agt_*")):
            metadata_path = directory / "metadata.json"
            bindings_path = directory / "bindings.json"
            if not metadata_path.is_file() or not bindings_path.is_file():
                continue
            metadata = read_json(metadata_path)
            bindings = read_json(bindings_path)
            records.append(
                AgentRecord(
                    agent_id=str(metadata["agent_id"]),
                    name=str(metadata["name"]),
                    runtime=str(metadata["runtime"]),
                    directory=directory,
                    metadata=metadata,
                    bindings=bindings,
                )
            )
        return records

    def resolve_agent(self, selector: str) -> AgentRecord:
        self.require_initialized()
        matches = [
            record
            for record in self.list_agents()
            if record.agent_id == selector or record.name.casefold() == selector.casefold()
        ]
        if not matches:
            raise NotFoundError(f"Agent not found: {selector}")
        if len(matches) > 1:
            raise ConflictError(f"Agent selector is ambiguous: {selector}")
        return matches[0]

    def update_bindings(self, agent: AgentRecord, values: dict[str, Any]) -> AgentRecord:
        current = read_json(agent.directory / "bindings.json")
        current.update(values)
        current["updated_at"] = utc_now()
        atomic_write_json(agent.directory / "bindings.json", current)
        return self.resolve_agent(agent.agent_id)

    def append_system_event(self, event: str, details: dict[str, Any] | None = None) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        record = {
            "schema_version": 1,
            "timestamp": utc_now(),
            "event": event,
            "details": details or {},
        }
        path = self.logs_dir / "agenty.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(path, 0o600)
