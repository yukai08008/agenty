from pathlib import Path

from agenty.application import run_registered_task
from agenty.task_registry import load_registry


def test_anna_registered_task_offline():
    root = Path(__file__).parents[1]
    registry_path = root / "agents" / "task_registry.json"
    task = load_registry(registry_path, workspace_root=root).by_id("anna-user-task")
    assert task.enabled is False
    result = run_registered_task(
        registry_path,
        workspace_root=root,
        task_id=task.task_id,
        runtime_executor=lambda _task, _context: {"success": True, "mode": "offline"},
        run_id="anna-offline-acceptance",
    )
    assert result.context.identity.agent_id == "anna"
    assert result.snapshot.state.value == "closed"
    assert result.context.manifest.manifest_sha256
