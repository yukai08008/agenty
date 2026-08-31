"""Crash-recoverable per-Agent state machines."""

from __future__ import annotations

import copy
import json
import os
import uuid
from pathlib import Path
from typing import Any

from agenty.store import AgentyError, atomic_write_json, file_lock, read_json, utc_now


LIFECYCLE_TRANSITIONS = {
    "CLAIMED": {"WORKER", "ARCHIVED"},
    "WORKER": {"MIGRATING", "ARCHIVED"},
    "MIGRATING": {"WORKER", "PROJECT"},
    "PROJECT": {"ARCHIVED"},
    "ARCHIVED": set(),
}

EXECUTION_TRANSITIONS = {
    "IDLE": {"STARTING"},
    "STARTING": {"RUNNING", "FAILED", "IDLE"},
    "RUNNING": {"WAITING", "BLOCKED", "STOPPING", "IDLE", "FAILED"},
    "WAITING": {"RUNNING", "BLOCKED", "STOPPING", "IDLE", "FAILED"},
    "BLOCKED": {"RUNNING", "STOPPING", "IDLE", "FAILED"},
    "STOPPING": {"IDLE", "FAILED"},
    "FAILED": {"IDLE", "STARTING"},
}

TASK_TRANSITIONS = {
    "NONE": {"ACTIVE"},
    "ACTIVE": {"WAITING_INPUT", "COMPLETED", "FAILED", "CANCELLED"},
    "WAITING_INPUT": {"ACTIVE", "COMPLETED", "FAILED", "CANCELLED"},
    "COMPLETED": {"NONE", "ACTIVE"},
    "FAILED": {"NONE", "ACTIVE"},
    "CANCELLED": {"NONE", "ACTIVE"},
}


class StateTransitionError(AgentyError):
    """Raised when a requested state transition is not allowed."""


class AgentStateMachine:
    """Persist one Agent's lifecycle, execution, and task state."""

    def __init__(self, agent_dir: Path) -> None:
        self.agent_dir = Path(agent_dir)
        self.state_dir = self.agent_dir / "state"
        self.current_path = self.state_dir / "current.json"
        self.events_path = self.state_dir / "events.jsonl"
        self.checkpoints_dir = self.state_dir / "checkpoints"
        self.lock_path = self.state_dir / ".lock"

    def bootstrap(self, agent_id: str) -> dict[str, Any]:
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with file_lock(self.lock_path):
            if self.current_path.exists() or self.events_path.exists():
                raise AgentyError(f"Agent state already exists: {self.agent_dir}")
            state = {
                "schema_version": 1,
                "revision": 0,
                "agent_id": agent_id,
                "lifecycle": {"phase": "CLAIMED"},
                "execution": {"status": "IDLE", "runtime_pid": None},
                "task": {
                    "status": "NONE",
                    "task_id": None,
                    "session_id": None,
                    "summary": None,
                },
                "recovery": {
                    "last_checkpoint": None,
                    "pending_action": None,
                    "resume_token": None,
                },
                "updated_at": utc_now(),
            }
            self._append_event_unlocked(
                revision=0,
                event="agent.claimed",
                axis="lifecycle",
                previous=None,
                current="CLAIMED",
                state=state,
                details={},
            )
            atomic_write_json(self.current_path, state)
            return state

    def load(self) -> dict[str, Any]:
        with file_lock(self.lock_path):
            return self._load_unlocked()

    def history(self, tail: int | None = None) -> list[dict[str, Any]]:
        with file_lock(self.lock_path):
            events = self._read_events_unlocked()
        if tail is not None:
            return events[-max(0, tail) :]
        return events

    def transition(
        self,
        axis: str,
        target: str,
        event: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with file_lock(self.lock_path):
            state = self._load_unlocked()
            field, transitions = self._axis_definition(axis)
            previous = str(state[axis][field])
            allowed = transitions.get(previous, set())
            if target not in allowed:
                raise StateTransitionError(
                    f"Invalid {axis} transition: {previous} -> {target}"
                )
            next_state = copy.deepcopy(state)
            next_state[axis][field] = target
            if axis == "execution" and target in {"IDLE", "FAILED"}:
                next_state[axis]["runtime_pid"] = None
            return self._commit_unlocked(
                state,
                next_state,
                event,
                axis,
                previous,
                target,
                details or {},
            )

    def set_runtime_pid(self, pid: int) -> dict[str, Any]:
        with file_lock(self.lock_path):
            state = self._load_unlocked()
            if state["execution"]["status"] not in {"STARTING", "RUNNING"}:
                raise StateTransitionError("Runtime PID can only be set while starting or running.")
            next_state = copy.deepcopy(state)
            next_state["execution"]["runtime_pid"] = pid
            return self._commit_unlocked(
                state,
                next_state,
                "runtime.pid_recorded",
                "execution",
                state["execution"]["status"],
                state["execution"]["status"],
                {"pid": pid},
            )

    def start_task(
        self,
        summary: str,
        *,
        task_id: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        with file_lock(self.lock_path):
            state = self._load_unlocked()
            previous = str(state["task"]["status"])
            if "ACTIVE" not in TASK_TRANSITIONS.get(previous, set()):
                raise StateTransitionError(f"Invalid task transition: {previous} -> ACTIVE")
            next_state = copy.deepcopy(state)
            next_state["task"] = {
                "status": "ACTIVE",
                "task_id": task_id or f"task_{uuid.uuid4().hex}",
                "session_id": session_id,
                "summary": summary,
            }
            return self._commit_unlocked(
                state,
                next_state,
                "task.started",
                "task",
                previous,
                "ACTIVE",
                {
                    "task_id": next_state["task"]["task_id"],
                    "session_id": session_id,
                },
            )

    def finish_task(self, status: str = "COMPLETED") -> dict[str, Any]:
        if status not in {"COMPLETED", "FAILED", "CANCELLED"}:
            raise StateTransitionError(f"Invalid terminal task status: {status}")
        with file_lock(self.lock_path):
            state = self._load_unlocked()
            previous = str(state["task"]["status"])
            if status not in TASK_TRANSITIONS.get(previous, set()):
                raise StateTransitionError(
                    f"Invalid task transition: {previous} -> {status}"
                )
            next_state = copy.deepcopy(state)
            next_state["task"]["status"] = status
            return self._commit_unlocked(
                state,
                next_state,
                f"task.{status.lower()}",
                "task",
                previous,
                status,
                {"task_id": state["task"].get("task_id")},
            )

    def checkpoint(
        self, payload: dict[str, Any] | None = None, summary: str | None = None
    ) -> tuple[str, dict[str, Any]]:
        with file_lock(self.lock_path):
            state = self._load_unlocked()
            revision = int(state["revision"]) + 1
            checkpoint_id = f"cp_{revision:06d}"
            checkpoint = {
                "schema_version": 1,
                "checkpoint_id": checkpoint_id,
                "agent_id": state["agent_id"],
                "revision": revision,
                "summary": summary,
                "payload": payload or {},
                "state": state,
                "created_at": utc_now(),
            }
            atomic_write_json(self.checkpoints_dir / f"{checkpoint_id}.json", checkpoint)

            next_state = copy.deepcopy(state)
            next_state["recovery"]["last_checkpoint"] = checkpoint_id
            next_state["recovery"]["pending_action"] = (
                payload or {}
            ).get("pending_action")
            committed = self._commit_unlocked(
                state,
                next_state,
                "agent.checkpointed",
                "recovery",
                state["recovery"].get("last_checkpoint"),
                checkpoint_id,
                {"summary": summary},
            )
            return checkpoint_id, committed

    def _axis_definition(self, axis: str) -> tuple[str, dict[str, set[str]]]:
        if axis == "lifecycle":
            return "phase", LIFECYCLE_TRANSITIONS
        if axis == "execution":
            return "status", EXECUTION_TRANSITIONS
        if axis == "task":
            return "status", TASK_TRANSITIONS
        raise StateTransitionError(f"Unknown state axis: {axis}")

    def _load_unlocked(self) -> dict[str, Any]:
        events = self._read_events_unlocked()
        latest_event_state = events[-1].get("state") if events else None

        try:
            current = read_json(self.current_path)
        except AgentyError:
            if not isinstance(latest_event_state, dict):
                raise
            current = copy.deepcopy(latest_event_state)
            atomic_write_json(self.current_path, current)
            return current

        if isinstance(latest_event_state, dict):
            event_revision = int(latest_event_state.get("revision", -1))
            current_revision = int(current.get("revision", -1))
            if event_revision > current_revision:
                current = copy.deepcopy(latest_event_state)
                atomic_write_json(self.current_path, current)
            elif current_revision > event_revision:
                raise AgentyError(
                    "State snapshot is ahead of the event log; refusing unsafe recovery."
                )
        return current

    def _read_events_unlocked(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        events = []
        for line_number, line in enumerate(
            self.events_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AgentyError(
                    f"Invalid state event JSON at line {line_number}: {exc.msg}"
                ) from exc
            if not isinstance(value, dict):
                raise AgentyError(f"State event at line {line_number} must be an object.")
            events.append(value)
        return events

    def _commit_unlocked(
        self,
        previous_state: dict[str, Any],
        next_state: dict[str, Any],
        event: str,
        axis: str,
        previous: Any,
        current: Any,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        next_state["revision"] = int(previous_state["revision"]) + 1
        next_state["updated_at"] = utc_now()
        self._append_event_unlocked(
            revision=int(next_state["revision"]),
            event=event,
            axis=axis,
            previous=previous,
            current=current,
            state=next_state,
            details=details,
        )
        atomic_write_json(self.current_path, next_state)
        return next_state

    def _append_event_unlocked(
        self,
        *,
        revision: int,
        event: str,
        axis: str,
        previous: Any,
        current: Any,
        state: dict[str, Any],
        details: dict[str, Any],
    ) -> None:
        record = {
            "schema_version": 1,
            "revision": revision,
            "timestamp": utc_now(),
            "event": event,
            "axis": axis,
            "from": previous,
            "to": current,
            "details": details,
            "state": state,
        }
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(self.events_path, 0o600)
