"""Offline-first composition of Registry, Harness, AgentyMachine and Runtime."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from agenty.harness import ResolvedContext, resolve_context
from agenty.machine import Action, AgentEvent, AgentyMachine, Environment, Goal, Reward
from agenty.task_registry import TaskSpec, load_registry
from agenty.run import run_opencode_task


class AgentRunResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    task: TaskSpec
    context: ResolvedContext
    snapshot: Any
    runtime_result: Any


def persist_agent_result(result: AgentRunResult, output_directory: str | Path) -> Path:
    """Persist one outcome in an explicit runtime-data directory."""
    directory = Path(output_directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    run_id = result.context.manifest.run_id
    target = directory / f"{run_id}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(result.model_dump_json(indent=2) + "\n")
    temporary.replace(target)
    return target


def run_registered_task(
    registry_path: str | Path,
    *,
    workspace_root: str | Path,
    task_id: str,
    runtime_executor: Callable[[TaskSpec, ResolvedContext], Any],
    run_id: str = "agent-run",
) -> AgentRunResult:
    """Compose one registered task without owning a specific Runtime adapter."""
    registry = load_registry(registry_path, workspace_root=workspace_root)
    task = registry.by_id(task_id)
    context = resolve_context(workspace_root, agent_root=task.agent_root, run_id=run_id)
    machine = AgentyMachine(
        Goal(goal_id=task.task_id, description=task.task_id),
        Environment(environment_id=task.executor_agent_id, working_directory=str(workspace_root)),
    )
    machine.apply(AgentEvent.CONTEXT_RESOLUTION_STARTED)
    machine.apply(AgentEvent.CONTEXT_RESOLVED)
    machine.apply(
        AgentEvent.PLAN_CREATED,
        action=Action(action_id=f"{run_id}-action", strategy="runtime_turn"),
    )
    machine.apply(AgentEvent.EXECUTION_STARTED)
    runtime_result = runtime_executor(task, context)
    success = bool(getattr(runtime_result, "success", runtime_result is not None))
    machine.apply(
        AgentEvent.RESULT_COLLECTED,
        reward=Reward(success=success, value=1.0 if success else 0.0),
    )
    machine.apply(AgentEvent.CLOSED)
    return AgentRunResult(task=task, context=context, snapshot=machine.snapshot(), runtime_result=runtime_result)


def run_registered_opencode_task(
    registry_path: str | Path,
    *,
    workspace_root: str | Path,
    task_id: str,
    auto_approve: bool = False,
    timeout_seconds: float = 300,
    executable: str = "opencode",
    run_id: str = "agent-run",
) -> AgentRunResult:
    """Run a registered task through the existing exact-version OpenCode entry point."""
    registry = load_registry(registry_path, workspace_root=workspace_root)
    task = registry.by_id(task_id)
    task_path = Path(task.task_file).expanduser().resolve()
    prompt = task_path.read_text().strip()
    return run_registered_task(
        registry_path,
        workspace_root=workspace_root,
        task_id=task_id,
        run_id=run_id,
        runtime_executor=lambda _task, _context: run_opencode_task(
            prompt,
            working_directory=workspace_root,
            auto_approve=auto_approve,
            timeout_seconds=timeout_seconds,
            executable=executable,
        ),
    )
