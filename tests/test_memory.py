import json

import pytest

from agenty.harness import resolve_context
from agenty.memory import MemoryWriteError, write_memory


def _context(tmp_path):
    for path, agent_id in [(tmp_path, "root"), (tmp_path / "agents" / "demo", "demo")]:
        path.mkdir(parents=True, exist_ok=True)
        (path / "AGENTS.md").write_text("rules")
        (path / "Identity.md").write_text(f"- Agent ID: `{agent_id}`\n- Name: `{agent_id}`\n")
        (path / "MEMORY.json").write_text(json.dumps({"status": "old", "stable": 1}))
    return resolve_context(tmp_path, agent_root=tmp_path / "agents" / "demo", run_id="run-7")


def test_writes_memory_to_explicit_loaded_layer_with_audit(tmp_path):
    context = _context(tmp_path)
    target = tmp_path / "agents" / "demo"
    audit = write_memory(context, target_layer=target, updates={"status": "new", "added": True}, audit_directory=tmp_path / "runtime")
    assert json.loads((target / "MEMORY.json").read_text())["status"] == "new"
    assert audit.changed_fields == ["added", "status"]
    assert audit.conflicting_fields == ["status"]
    assert (tmp_path / "runtime" / "run-7-memory.json").is_file()


def test_rejects_memory_write_outside_loaded_layers(tmp_path):
    context = _context(tmp_path)
    with pytest.raises(MemoryWriteError, match="loaded"):
        write_memory(context, target_layer=tmp_path / "other", updates={"x": 1}, audit_directory=tmp_path / "runtime")
