import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agenty.state import AgentStateMachine
from agenty.store import AgentyStore, ConflictError
from agenty.workspace import create_worker, migrate_worker


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = AgentyStore(self.root / "home", self.root / "workers")
        self.store.initialize()
        self.store.add_runtime("mock", [sys.executable, "-c", "pass"])
        self.agent = self.store.claim("worker-agent", "mock")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_worker_uses_default_agents_home(self):
        updated = create_worker(self.store, self.agent.agent_id)

        expected = (self.root / "workers" / "worker-agent").resolve()
        self.assertEqual(Path(updated.bindings["active_root"]), expected)
        self.assertTrue((expected / "agent-suite").is_dir())
        state = AgentStateMachine(self.agent.directory).load()
        self.assertEqual(state["lifecycle"]["phase"], "WORKER")

    def test_create_worker_rejects_non_empty_target(self):
        target = self.root / "occupied"
        target.mkdir()
        (target / "user-file.txt").write_text("valuable", encoding="utf-8")

        with self.assertRaises(ConflictError):
            create_worker(self.store, self.agent.agent_id, target)

        self.assertEqual((target / "user-file.txt").read_text(), "valuable")

    def test_migration_preserves_identity_history_source_and_initializes_git(self):
        worker = create_worker(self.store, self.agent.agent_id)
        source = Path(worker.bindings["active_root"])
        (source / "workspace" / "work.txt").write_text("keep", encoding="utf-8")
        target = self.root / "project"

        migrated = migrate_worker(
            self.store, self.agent.agent_id, target, init_git=True
        )

        state = AgentStateMachine(self.agent.directory).load()
        self.assertEqual(migrated.agent_id, self.agent.agent_id)
        self.assertEqual(state["lifecycle"]["phase"], "PROJECT")
        self.assertTrue(source.is_dir())
        self.assertEqual((target / "workspace" / "work.txt").read_text(), "keep")
        self.assertTrue((target / ".git").is_dir())
        git_check = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(git_check.stdout.strip(), "true")
        events = [event["event"] for event in AgentStateMachine(self.agent.directory).history()]
        self.assertIn("migration.started", events)
        self.assertIn("migration.completed", events)

    def test_migration_rejects_non_empty_and_child_targets(self):
        worker = create_worker(self.store, self.agent.agent_id)
        source = Path(worker.bindings["active_root"])
        occupied = self.root / "occupied-project"
        occupied.mkdir()
        (occupied / "important.txt").write_text("do not overwrite", encoding="utf-8")

        with self.assertRaises(ConflictError):
            migrate_worker(self.store, self.agent.agent_id, occupied)
        with self.assertRaises(ConflictError):
            migrate_worker(self.store, self.agent.agent_id, source / "nested")

        self.assertEqual((occupied / "important.txt").read_text(), "do not overwrite")


if __name__ == "__main__":
    unittest.main()
