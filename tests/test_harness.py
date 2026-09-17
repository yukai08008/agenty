import json
from pathlib import Path

import pytest

from agenty.harness import HarnessError, resolve_context


def _layer(path, agent_id, memory, skill=None):
    path.mkdir(parents=True, exist_ok=True)
    (path / "AGENTS.md").write_text(f"rules for {agent_id}\n")
    (path / "Identity.md").write_text(f"- Agent ID: `{agent_id}`\n- Name: `{agent_id.title()}`\n")
    (path / "MEMORY.json").write_text(json.dumps(memory))
    if skill:
        skills = path / "skills"
        skills.mkdir()
        (skills / f"{skill}.md").write_text("skill")


def test_resolves_layers_and_merges_nearest_values(tmp_path):
    _layer(tmp_path, "root", {"notification": {"mode": "event_only"}, "keep": 1}, "base")
    agents = tmp_path / "agents"
    _layer(agents, "public", {"notification": {"mode": "shared"}}, "shared")
    agent = agents / "anna"
    _layer(agent, "anna", {"notification": {"mode": "private"}, "clear": None}, "private")
    context = resolve_context(tmp_path, agent_root=agent, run_id="run-1")
    assert context.identity.agent_id == "anna"
    assert context.memory == {"notification": {"mode": "private"}, "keep": 1}
    assert set(context.skills) == {"base", "shared", "private"}
    assert context.manifest.run_id == "run-1"


def test_rejects_agent_path_escape(tmp_path):
    with pytest.raises(HarnessError, match="escapes"):
        resolve_context(tmp_path, agent_root=tmp_path.parent / "outside")


def test_rejects_incomplete_agent_layer(tmp_path):
    agent = tmp_path / "anna"
    agent.mkdir()
    (agent / "AGENTS.md").write_text("rules")
    with pytest.raises(HarnessError, match="incomplete"):
        resolve_context(tmp_path, agent_root=agent)


def test_child_permissions_cannot_expand_parent_ceiling(tmp_path):
    _layer(tmp_path, "root", {})
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "permissions.json").write_text(
        json.dumps({"permissions": {"tools": ["read", "inspect"], "mutate": False}})
    )
    agent = tmp_path / "anna"
    _layer(agent, "anna", {})
    (agent / "config").mkdir()
    (agent / "config" / "permissions.json").write_text(
        json.dumps({"permissions": {"tools": ["read"], "mutate": True}})
    )
    context = resolve_context(tmp_path, agent_root=agent)
    assert context.permissions == {"tools": ["read"], "mutate": False}


def test_manifest_digest_is_stable(tmp_path):
    _layer(tmp_path, "root", {})
    agent = tmp_path / "anna"
    _layer(agent, "anna", {})
    first = resolve_context(tmp_path, agent_root=agent).manifest.manifest_sha256
    second = resolve_context(tmp_path, agent_root=agent).manifest.manifest_sha256
    assert first == second


def test_demo_workspace_fixture_resolves():
    root = Path(__file__).parent / "fixtures" / "demo_workspace"
    context = resolve_context(root, agent_root=root / "agents" / "demo", task_directory=root / "agents" / "demo")
    assert context.identity.agent_id == "demo"
    assert context.memory["notification"]["mode"] == "agent"
