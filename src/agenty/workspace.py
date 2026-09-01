"""Worker workspace lifecycle and safe project migration."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from agenty.state import AgentStateMachine
from agenty.store import AgentRecord, AgentyError, AgentyStore, ConflictError
from agenty.suite import append_event, create_suite, inspect_suite, update_gitignore


def create_worker(
    store: AgentyStore,
    selector: str,
    path: Path | str | None = None,
) -> AgentRecord:
    agent = store.resolve_agent(selector)
    machine = AgentStateMachine(agent.directory)
    state = machine.load()
    if state["lifecycle"]["phase"] != "CLAIMED":
        raise ConflictError(
            f"Agent must be CLAIMED to create a Worker; current phase is "
            f"{state['lifecycle']['phase']}."
        )
    if state["execution"]["status"] != "IDLE":
        raise ConflictError("Agent must be IDLE to create a Worker workspace.")

    root = (
        Path(path).expanduser().resolve()
        if path is not None
        else (store.agents_home / agent.name).resolve()
    )
    _require_empty_target(root)
    root.mkdir(parents=True, exist_ok=True)
    create_suite(root, agent.agent_id, agent.name)
    append_event(
        root,
        "workspace.created",
        "Worker workspace created",
        {"agent_id": agent.agent_id, "root": str(root)},
    )

    machine.transition(
        "lifecycle",
        "WORKER",
        "workspace.created",
        {"root": str(root)},
    )
    updated = store.update_bindings(
        agent,
        {
            "active_root": str(root),
            "suite": str(root / "agent-suite"),
            "workspace": str(root / "workspace"),
            "project": None,
            "retained_source": None,
        },
    )
    store.append_system_event(
        "workspace.created", {"agent_id": agent.agent_id, "root": str(root)}
    )
    return updated


def migrate_worker(
    store: AgentyStore,
    selector: str,
    target: Path | str,
    *,
    init_git: bool = False,
) -> AgentRecord:
    agent = store.resolve_agent(selector)
    machine = AgentStateMachine(agent.directory)
    state = machine.load()
    if state["lifecycle"]["phase"] != "WORKER":
        raise ConflictError(
            f"Agent must be WORKER to migrate; current phase is "
            f"{state['lifecycle']['phase']}."
        )
    if state["execution"]["status"] != "IDLE":
        raise ConflictError("Agent must be IDLE before migration.")

    source_value = agent.bindings.get("active_root")
    if not isinstance(source_value, str):
        raise AgentyError("Worker binding has no active_root.")
    source = Path(source_value).resolve()
    destination = Path(target).expanduser().resolve()
    if destination == source:
        raise ConflictError("Migration target must differ from the current Worker root.")
    if _is_relative_to(destination, source):
        raise ConflictError("Migration target cannot be inside the current Worker root.")
    _require_empty_target(destination)

    checkpoint_id, _ = machine.checkpoint(
        {
            "pending_action": "migrate",
            "source": str(source),
            "target": str(destination),
        },
        summary="Before Worker to Project migration",
    )
    machine.transition(
        "lifecycle",
        "MIGRATING",
        "migration.started",
        {
            "source": str(source),
            "target": str(destination),
            "checkpoint": checkpoint_id,
        },
    )

    try:
        if destination.exists():
            shutil.copytree(
                source,
                destination,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".git"),
            )
        else:
            shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".git"))
        if init_git:
            result = subprocess.run(
                ["git", "init", str(destination)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise AgentyError(result.stderr.strip() or "git init failed")
        update_gitignore(destination)
        inspection = inspect_suite(destination)
        if not inspection.valid:
            raise AgentyError("Migrated suite is invalid: " + "; ".join(inspection.errors))

        updated = store.update_bindings(
            agent,
            {
                "active_root": str(destination),
                "suite": str(destination / "agent-suite"),
                "workspace": str(destination / "workspace"),
                "project": str(destination),
                "retained_source": str(source),
            },
        )
        machine.transition(
            "lifecycle",
            "PROJECT",
            "migration.completed",
            {
                "source": str(source),
                "target": str(destination),
                "git_initialized": init_git,
            },
        )
        append_event(
            destination,
            "agent.migrated",
            "Worker migrated to a project root",
            {
                "agent_id": agent.agent_id,
                "source": str(source),
                "target": str(destination),
            },
        )
        store.append_system_event(
            "agent.migrated",
            {
                "agent_id": agent.agent_id,
                "source": str(source),
                "target": str(destination),
            },
        )
        return updated
    except Exception as exc:
        machine.transition(
            "lifecycle",
            "WORKER",
            "migration.failed",
            {"target": str(destination), "error": str(exc)},
        )
        raise


def _require_empty_target(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ConflictError(f"Target path is not a directory: {path}")
    if path.exists() and any(path.iterdir()):
        raise ConflictError(f"Target directory is not empty: {path}")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
