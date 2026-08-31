"""Agent suite creation, validation, semantic events, and snapshot scenario."""

from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from agenty.store import AgentyError, atomic_write_json, atomic_write_text, utc_now


SUITE_DIR_NAME = "agent-suite"
EVENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
REQUIRED_FILES = ("AGENTS.md", "MEMORY.json", "agent_log.jsonl")
REQUIRED_DIRS = ("skills", "memory", "sessions")

GITIGNORE_ENTRIES = (
    "agent-suite/skills/user_skills/",
    "agent-suite/memory/",
    "agent-suite/sessions/",
    "agent-suite/agent_log.jsonl",
    "agent-suite/.lock",
)

AGENTS_TEMPLATE = """# {name}

## Identity

- Agent ID: `{agent_id}`
- Lifecycle is managed by Agenty; do not create a second identity for this workspace.

## Bootstrap

1. Read `MEMORY.json` for verified key facts.
2. Load only task-relevant capabilities from `skills/`.
3. Search `memory/` only when detailed historical context is required.
4. Use `sessions/` to resume unfinished transactional work.
5. Record important semantic operations in `agent_log.jsonl`.

## Boundaries

- Treat project files and user data as valuable state.
- Do not perform destructive or external actions without appropriate authority.
- Keep `MEMORY.json` concise, current, and verifiable.
- Do not confuse Agenty runtime state under `~/.agenty` with project knowledge.
"""

SNAPSHOT_SKILL = """---
name: project-snapshot
description: >-
  Produce a deterministic project inventory and persist it as Agent memory
  and session evidence.
---

# Project snapshot

1. Read the suite `AGENTS.md` and `MEMORY.json`.
2. Count files in `workspace/` and detect whether the root is a Git work tree.
3. Capture a concise Git status when Git is available.
4. Write the detailed result to `memory/`.
5. Write a completed transactional record to `sessions/`.
6. Update the `latest-project-snapshot` fact in `MEMORY.json`.
7. Append semantic start and completion events to `agent_log.jsonl`.
"""


class SuiteError(AgentyError):
    """Raised when an agent suite is missing, invalid, or unsafe to modify."""


@dataclass(frozen=True)
class InspectionResult:
    root: Path
    agent_id: str | None
    agent_name: str | None
    fact_count: int
    event_count: int
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def validate_event_name(name: str) -> str:
    value = name.strip()
    if not EVENT_NAME_PATTERN.fullmatch(value):
        raise SuiteError(
            "Event name must start with a lowercase letter and contain lowercase "
            "letters, numbers, dots, underscores, or hyphens."
        )
    return value


def create_suite(root: Path | str, agent_id: str, agent_name: str) -> Path:
    workspace_root = Path(root).expanduser().resolve()
    suite_root = workspace_root / SUITE_DIR_NAME
    if suite_root.exists():
        raise SuiteError(f"Agent suite already exists: {suite_root}")

    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "workspace").mkdir(exist_ok=True)
    (suite_root / "skills" / "project-snapshot").mkdir(parents=True)
    (suite_root / "skills" / "user_skills").mkdir()
    (suite_root / "memory").mkdir()
    (suite_root / "sessions").mkdir()

    atomic_write_text(
        suite_root / "AGENTS.md",
        AGENTS_TEMPLATE.format(name=agent_name, agent_id=agent_id),
    )
    bootstrap_path = workspace_root / "AGENTS.md"
    if not bootstrap_path.exists():
        bootstrap_path.symlink_to(Path(SUITE_DIR_NAME) / "AGENTS.md")
    atomic_write_text(
        suite_root / "skills" / "project-snapshot" / "SKILL.md",
        SNAPSHOT_SKILL,
    )

    memory = {
        "schema_version": 1,
        "agent": {
            "agent_id": agent_id,
            "name": agent_name,
            "purpose": "Develop, manage, and maintain work in this workspace.",
        },
        "facts": [],
        "updated_at": utc_now(),
    }
    atomic_write_json(suite_root / "MEMORY.json", memory)
    (suite_root / "agent_log.jsonl").touch(mode=0o600)
    append_event(
        workspace_root,
        "suite.initialized",
        "Agent suite initialized",
        {"agent_id": agent_id},
    )
    update_gitignore(workspace_root)
    return suite_root


def append_event(
    root: Path | str,
    event: str,
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workspace_root = Path(root).expanduser().resolve()
    suite_root = workspace_root / SUITE_DIR_NAME
    if not suite_root.is_dir():
        raise SuiteError(f"Agent suite not found: {suite_root}")

    record: dict[str, Any] = {
        "schema_version": 1,
        "event_id": f"evt_{uuid.uuid4().hex}",
        "timestamp": utc_now(),
        "event": validate_event_name(event),
        "details": details or {},
    }
    if message:
        record["message"] = message

    log_path = suite_root / "agent_log.jsonl"
    with _suite_lock(suite_root):
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
            log_file.flush()
            os.fsync(log_file.fileno())
        os.chmod(log_path, 0o600)
    return record


def inspect_suite(root: Path | str) -> InspectionResult:
    workspace_root = Path(root).expanduser().resolve()
    suite_root = workspace_root / SUITE_DIR_NAME
    errors: list[str] = []
    agent_id: str | None = None
    agent_name: str | None = None
    fact_count = 0
    event_count = 0

    if not suite_root.is_dir():
        return InspectionResult(
            workspace_root,
            None,
            None,
            0,
            0,
            (f"Missing directory: {SUITE_DIR_NAME}",),
        )

    for relative_path in REQUIRED_FILES:
        if not (suite_root / relative_path).is_file():
            errors.append(f"Missing file: {SUITE_DIR_NAME}/{relative_path}")
    for relative_path in REQUIRED_DIRS:
        if not (suite_root / relative_path).is_dir():
            errors.append(f"Missing directory: {SUITE_DIR_NAME}/{relative_path}")
    if not (suite_root / "skills" / "user_skills").is_dir():
        errors.append(f"Missing directory: {SUITE_DIR_NAME}/skills/user_skills")
    if not (suite_root / "skills" / "project-snapshot" / "SKILL.md").is_file():
        errors.append("Missing built-in skill: project-snapshot")

    memory_path = suite_root / "MEMORY.json"
    if memory_path.is_file():
        try:
            memory = json.loads(memory_path.read_text(encoding="utf-8"))
            memory_errors, agent_id, agent_name, fact_count = _validate_memory(memory)
            errors.extend(memory_errors)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"Invalid MEMORY.json: {exc}")

    log_path = suite_root / "agent_log.jsonl"
    if log_path.is_file():
        try:
            for line_number, raw_line in enumerate(
                log_path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not raw_line.strip():
                    continue
                event_count += 1
                try:
                    event_record = json.loads(raw_line)
                    event_error = _validate_event_record(event_record)
                    if event_error:
                        errors.append(f"Invalid event at line {line_number}: {event_error}")
                except json.JSONDecodeError as exc:
                    errors.append(f"Invalid event JSON at line {line_number}: {exc.msg}")
        except (OSError, UnicodeError) as exc:
            errors.append(f"Cannot read agent_log.jsonl: {exc}")

    return InspectionResult(
        workspace_root,
        agent_id,
        agent_name,
        fact_count,
        event_count,
        tuple(errors),
    )


def create_project_snapshot(root: Path | str) -> dict[str, Any]:
    workspace_root = Path(root).expanduser().resolve()
    suite_root = workspace_root / SUITE_DIR_NAME
    result = inspect_suite(workspace_root)
    if not result.valid:
        raise SuiteError("Cannot snapshot invalid suite: " + "; ".join(result.errors))

    append_event(workspace_root, "snapshot.started", "Project snapshot started")
    project_dir = workspace_root / "workspace"
    project_files = sorted(path for path in project_dir.rglob("*") if path.is_file())
    git_root = workspace_root if (workspace_root / ".git").exists() else project_dir
    is_git = _is_git_work_tree(git_root)
    git_status = _git_status(git_root) if is_git else None
    timestamp = utc_now()
    artifact_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_id += f"-{uuid.uuid4().hex[:8]}"

    snapshot = {
        "schema_version": 1,
        "snapshot_id": f"snapshot-{artifact_id}",
        "agent_id": result.agent_id,
        "created_at": timestamp,
        "workspace": str(project_dir),
        "file_count": len(project_files),
        "git": {"is_work_tree": is_git, "status": git_status},
    }
    memory_path = suite_root / "memory" / f"project-snapshot-{artifact_id}.json"
    session_path = suite_root / "sessions" / f"snapshot-{artifact_id}.json"
    atomic_write_json(memory_path, snapshot)
    atomic_write_json(
        session_path,
        {
            "schema_version": 1,
            "session_id": f"session-{artifact_id}",
            "kind": "project-snapshot",
            "status": "completed",
            "snapshot": str(memory_path.relative_to(suite_root)),
            "created_at": timestamp,
        },
    )

    with _suite_lock(suite_root):
        memory = json.loads((suite_root / "MEMORY.json").read_text(encoding="utf-8"))
        facts = memory.setdefault("facts", [])
        facts[:] = [
            fact
            for fact in facts
            if not isinstance(fact, dict) or fact.get("id") != "latest-project-snapshot"
        ]
        facts.append(
            {
                "id": "latest-project-snapshot",
                "value": {
                    "snapshot_id": snapshot["snapshot_id"],
                    "file_count": snapshot["file_count"],
                    "git": is_git,
                    "memory_path": str(memory_path.relative_to(suite_root)),
                },
                "verified_at": timestamp,
            }
        )
        memory["updated_at"] = timestamp
        atomic_write_json(suite_root / "MEMORY.json", memory)

    append_event(
        workspace_root,
        "snapshot.completed",
        "Project snapshot completed",
        {
            "snapshot_id": snapshot["snapshot_id"],
            "file_count": snapshot["file_count"],
        },
    )
    return snapshot


def update_gitignore(root: Path | str) -> None:
    workspace_root = Path(root).expanduser().resolve()
    gitignore_path = workspace_root / ".gitignore"
    existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    existing_lines = existing.splitlines()
    missing = [entry for entry in GITIGNORE_ENTRIES if entry not in existing_lines]
    if not missing:
        return
    content = existing
    if content and not content.endswith("\n"):
        content += "\n"
    if content:
        content += "\n"
    content += "# Agenty local Agent state\n" + "\n".join(missing) + "\n"
    atomic_write_text(gitignore_path, content, mode=0o644)


@contextmanager
def _suite_lock(suite_root: Path) -> Iterator[None]:
    lock_path = suite_root / ".lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _validate_memory(
    memory: Any,
) -> tuple[list[str], str | None, str | None, int]:
    errors: list[str] = []
    if not isinstance(memory, dict):
        return ["MEMORY.json root must be an object"], None, None, 0
    if memory.get("schema_version") != 1:
        errors.append("MEMORY.json schema_version must be 1")
    agent = memory.get("agent")
    agent_id: str | None = None
    agent_name: str | None = None
    if not isinstance(agent, dict):
        errors.append("MEMORY.json agent must be an object")
    else:
        if isinstance(agent.get("agent_id"), str) and agent["agent_id"].startswith("agt_"):
            agent_id = agent["agent_id"]
        else:
            errors.append("MEMORY.json agent.agent_id must be an agt_ identifier")
        if isinstance(agent.get("name"), str) and agent["name"].strip():
            agent_name = agent["name"]
        else:
            errors.append("MEMORY.json agent.name must be a non-empty string")
        if not isinstance(agent.get("purpose"), str) or not agent.get("purpose", "").strip():
            errors.append("MEMORY.json agent.purpose must be a non-empty string")
    facts = memory.get("facts")
    fact_count = len(facts) if isinstance(facts, list) else 0
    if not isinstance(facts, list):
        errors.append("MEMORY.json facts must be an array")
    if not isinstance(memory.get("updated_at"), str):
        errors.append("MEMORY.json updated_at must be a string")
    return errors, agent_id, agent_name, fact_count


def _validate_event_record(record: Any) -> str | None:
    if not isinstance(record, dict):
        return "event must be an object"
    if record.get("schema_version") != 1:
        return "schema_version must be 1"
    if not isinstance(record.get("event_id"), str):
        return "event_id must be a string"
    if not isinstance(record.get("timestamp"), str):
        return "timestamp must be a string"
    if not isinstance(record.get("event"), str):
        return "event must be a string"
    try:
        validate_event_name(record["event"])
    except SuiteError as exc:
        return str(exc)
    if not isinstance(record.get("details"), dict):
        return "details must be an object"
    return None


def _is_git_work_tree(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _git_status(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--short"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"
