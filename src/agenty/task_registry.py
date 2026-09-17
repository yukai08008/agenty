"""Versioned task registry and readable TASK.md contract validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskRegistryError(ValueError):
    """A task registry is invalid or points outside its workspace."""


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    executor_agent_id: str
    agent_root: str
    task_file: str
    skill: str | None = None
    runtime_policy: dict[str, Any] = Field(default_factory=dict)
    permissions: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = False


class TaskRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    tasks: list[TaskSpec]

    def by_id(self, task_id: str) -> TaskSpec:
        matches = [task for task in self.tasks if task.task_id == task_id]
        if len(matches) != 1:
            raise TaskRegistryError(f"unknown task: {task_id}")
        return matches[0]


def load_registry(path: str | Path, *, workspace_root: str | Path) -> TaskRegistry:
    registry_path = Path(path).expanduser().resolve()
    root = Path(workspace_root).expanduser().resolve()
    try:
        registry_path.relative_to(root)
    except ValueError as exc:
        raise TaskRegistryError("registry path escapes workspace root") from exc
    try:
        payload = json.loads(registry_path.read_text())
        registry = TaskRegistry.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise TaskRegistryError(f"invalid task registry: {registry_path}") from exc
    ids = [task.task_id for task in registry.tasks]
    if len(ids) != len(set(ids)):
        raise TaskRegistryError("task IDs must be unique")
    for task in registry.tasks:
        agent_root = _safe(root, task.agent_root)
        task_file = _safe(root, task.task_file)
        if not (agent_root / "AGENTS.md").is_file() or not (agent_root / "Identity.md").is_file():
            raise TaskRegistryError(f"agent root is incomplete: {agent_root}")
        if not task_file.is_file():
            raise TaskRegistryError(f"task contract is missing: {task_file}")
        if "#" not in task_file.read_text():
            raise TaskRegistryError(f"task contract is not Markdown: {task_file}")
    return registry


def _safe(root: Path, value: str) -> Path:
    expanded = Path(value).expanduser()
    candidate = (expanded if expanded.is_absolute() else root / expanded).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise TaskRegistryError(f"path escapes workspace root: {value}") from exc
    return candidate
