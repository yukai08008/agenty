import json

import pytest

from agenty.task_registry import TaskRegistryError, load_registry


def test_loads_registry_and_task_contract(tmp_path):
    agent = tmp_path / "agents" / "demo"
    agent.mkdir(parents=True)
    (agent / "AGENTS.md").write_text("rules")
    (agent / "Identity.md").write_text("- Agent ID: `demo`\n- Name: `Demo`\n")
    (agent / "TASK.md").write_text("# Demo task\n")
    registry = tmp_path / "agents" / "registry.json"
    registry.write_text(json.dumps({"schema_version": 1, "tasks": [{
        "task_id": "demo-task", "executor_agent_id": "demo",
        "agent_root": str(agent), "task_file": str(agent / "TASK.md"), "enabled": True,
    }]}))
    loaded = load_registry(registry, workspace_root=tmp_path)
    assert loaded.by_id("demo-task").enabled is True


def test_rejects_duplicate_ids(tmp_path):
    registry = tmp_path / "registry.json"
    payload = {"tasks": [{"task_id": "x", "executor_agent_id": "a", "agent_root": ".", "task_file": "TASK.md"}] * 2}
    registry.write_text(json.dumps(payload))
    with pytest.raises(TaskRegistryError, match="unique"):
        load_registry(registry, workspace_root=tmp_path)
