import json

from agenty.application import persist_agent_result, run_registered_task
from agenty import application


def test_registered_task_composes_harness_and_machine(tmp_path):
    agent = tmp_path / "agents" / "demo"
    agent.mkdir(parents=True)
    (tmp_path / "AGENTS.md").write_text("root")
    (tmp_path / "Identity.md").write_text("- Agent ID: `root`\n- Name: `Root`\n")
    (tmp_path / "MEMORY.json").write_text("{}")
    (tmp_path / "agents" / "AGENTS.md").write_text("public")
    (tmp_path / "agents" / "Identity.md").write_text("- Agent ID: `public`\n- Name: `Public`\n")
    (tmp_path / "agents" / "MEMORY.json").write_text("{}")
    (agent / "AGENTS.md").write_text("demo")
    (agent / "Identity.md").write_text("- Agent ID: `demo`\n- Name: `Demo`\n")
    (agent / "MEMORY.json").write_text("{}")
    (agent / "TASK.md").write_text("# Demo task\n")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"tasks": [{"task_id": "demo", "executor_agent_id": "demo", "agent_root": str(agent), "task_file": str(agent / "TASK.md")}]}))

    result = run_registered_task(registry, workspace_root=tmp_path, task_id="demo", runtime_executor=lambda task, context: {"success": True})
    assert result.snapshot.state.value == "closed"
    assert result.context.identity.agent_id == "demo"
    output = persist_agent_result(result, tmp_path / "runtime-data")
    assert output.read_text().startswith('{')


def test_registered_opencode_uses_task_contract(monkeypatch, tmp_path):
    agent = tmp_path / "agents" / "demo"
    agent.mkdir(parents=True)
    for path, text in [
        (tmp_path / "AGENTS.md", "root"),
        (tmp_path / "Identity.md", "- Agent ID: `root`\n- Name: `Root`\n"),
        (tmp_path / "MEMORY.json", "{}"),
        (tmp_path / "agents" / "AGENTS.md", "public"),
        (tmp_path / "agents" / "Identity.md", "- Agent ID: `public`\n- Name: `Public`\n"),
        (tmp_path / "agents" / "MEMORY.json", "{}"),
        (agent / "AGENTS.md", "demo"),
        (agent / "Identity.md", "- Agent ID: `demo`\n- Name: `Demo`\n"),
        (agent / "MEMORY.json", "{}"),
        (agent / "TASK.md", "# Inspect repository\n"),
    ]:
        path.write_text(text)
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"tasks": [{"task_id": "demo", "executor_agent_id": "demo", "agent_root": str(agent), "task_file": str(agent / "TASK.md")}]}))
    calls = {}
    monkeypatch.setattr(application, "run_opencode_task", lambda prompt, **kwargs: calls.update(prompt=prompt, kwargs=kwargs) or type("Result", (), {"success": True})())
    result = application.run_registered_opencode_task(registry, workspace_root=tmp_path, task_id="demo")
    assert calls["prompt"] == "# Inspect repository"
    assert result.snapshot.state.value == "closed"
