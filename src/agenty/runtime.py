"""Launch external Agent runtimes while maintaining execution state."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from agenty.state import AgentStateMachine
from agenty.store import AgentyError, AgentyStore, atomic_write_json, utc_now


def launch_agent(
    store: AgentyStore,
    selector: str,
    extra_args: list[str] | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    agent = store.resolve_agent(selector)
    profile = store.get_runtime(agent.runtime)
    argv = list(profile.get("argv", [])) + list(extra_args or [])
    if not argv:
        raise AgentyError(f"Runtime profile has no argv: {agent.runtime}")

    active_root = agent.bindings.get("active_root")
    cwd = Path(active_root) if isinstance(active_root, str) else agent.directory / "scratch"
    command = {"argv": argv, "cwd": str(cwd), "runtime": agent.runtime}
    if dry_run:
        return {**command, "dry_run": True}

    machine = AgentStateMachine(agent.directory)
    state = machine.load()
    if state["execution"]["status"] not in {"IDLE", "FAILED"}:
        raise AgentyError(
            f"Agent cannot start while execution is {state['execution']['status']}."
        )
    if state["execution"]["status"] == "FAILED":
        machine.transition("execution", "IDLE", "runtime.failure_acknowledged")
    machine.transition("execution", "STARTING", "runtime.starting", command)

    try:
        process = subprocess.Popen(argv, cwd=cwd)
    except OSError as exc:
        machine.transition(
            "execution", "FAILED", "runtime.start_failed", {"error": str(exc)}
        )
        raise AgentyError(f"Cannot start runtime `{agent.runtime}`: {exc}") from exc

    handle = {
        "schema_version": 1,
        "runtime": agent.runtime,
        "argv": argv,
        "cwd": str(cwd),
        "pid": process.pid,
        "started_at": utc_now(),
    }
    atomic_write_json(agent.directory / "runtime" / "handle.json", handle)
    machine.set_runtime_pid(process.pid)
    machine.transition(
        "execution", "RUNNING", "runtime.started", {"pid": process.pid}
    )

    try:
        return_code = process.wait()
    except KeyboardInterrupt:
        process.terminate()
        machine.transition("execution", "STOPPING", "runtime.interrupted")
        process.wait()
        machine.transition("execution", "IDLE", "runtime.stopped")
        raise

    if return_code == 0:
        machine.transition(
            "execution", "IDLE", "runtime.exited", {"return_code": return_code}
        )
    else:
        machine.transition(
            "execution", "FAILED", "runtime.failed", {"return_code": return_code}
        )
    handle["return_code"] = return_code
    handle["finished_at"] = utc_now()
    atomic_write_json(agent.directory / "runtime" / "handle.json", handle)
    return {**command, "dry_run": False, "return_code": return_code}
