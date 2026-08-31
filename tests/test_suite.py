import json
import tempfile
import unittest
from pathlib import Path

from agenty.suite import create_project_snapshot, create_suite, inspect_suite


class AgentSuiteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "worker"
        self.suite = create_suite(self.root, "agt_test", "suite-agent")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_suite_builds_three_files_three_directories_and_skill(self):
        for name in ("AGENTS.md", "MEMORY.json", "agent_log.jsonl"):
            self.assertTrue((self.suite / name).is_file())
        for name in ("skills", "memory", "sessions"):
            self.assertTrue((self.suite / name).is_dir())
        self.assertTrue((self.suite / "skills" / "user_skills").is_dir())
        self.assertTrue(
            (self.suite / "skills" / "project-snapshot" / "SKILL.md").is_file()
        )
        self.assertTrue((self.root / "AGENTS.md").is_symlink())

        result = inspect_suite(self.root)
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.agent_id, "agt_test")

    def test_snapshot_exercises_memory_session_log_and_fast_memory(self):
        project_dir = self.root / "workspace"
        (project_dir / "README.md").write_text("demo", encoding="utf-8")
        (project_dir / "src").mkdir()
        (project_dir / "src" / "app.py").write_text("print('ok')", encoding="utf-8")

        snapshot = create_project_snapshot(self.root)

        self.assertEqual(snapshot["file_count"], 2)
        memory_files = list((self.suite / "memory").glob("project-snapshot-*.json"))
        session_files = list((self.suite / "sessions").glob("snapshot-*.json"))
        self.assertEqual(len(memory_files), 1)
        self.assertEqual(len(session_files), 1)
        memory = json.loads((self.suite / "MEMORY.json").read_text(encoding="utf-8"))
        self.assertEqual(memory["facts"][0]["id"], "latest-project-snapshot")
        events = (self.suite / "agent_log.jsonl").read_text(encoding="utf-8")
        self.assertIn("snapshot.started", events)
        self.assertIn("snapshot.completed", events)

    def test_inspection_reports_missing_component(self):
        (self.suite / "sessions").rmdir()
        result = inspect_suite(self.root)
        self.assertFalse(result.valid)
        self.assertIn("Missing directory: agent-suite/sessions", result.errors)


if __name__ == "__main__":
    unittest.main()
