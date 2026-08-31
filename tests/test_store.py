import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from agenty.store import AgentyStore, ConflictError


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.store = AgentyStore(root / "home", root / "workers")
        self.store.initialize()
        self.store.add_runtime("mock", [sys.executable, "-c", "pass"])

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_claims_multiple_isolated_agents(self):
        first = self.store.claim("alpha", "mock")
        second = self.store.claim("beta", "mock")

        self.assertNotEqual(first.agent_id, second.agent_id)
        self.assertNotEqual(first.directory, second.directory)
        self.assertEqual({agent.name for agent in self.store.list_agents()}, {"alpha", "beta"})
        self.assertEqual(self.store.resolve_agent("alpha").agent_id, first.agent_id)
        self.assertEqual(self.store.resolve_agent(second.agent_id).name, "beta")

    def test_duplicate_name_is_rejected_case_insensitively(self):
        self.store.claim("Alpha", "mock")
        with self.assertRaises(ConflictError):
            self.store.claim("alpha", "mock")

    def test_control_plane_and_state_files_are_private(self):
        agent = self.store.claim("private-agent", "mock")

        home_mode = stat.S_IMODE(os.stat(self.store.home).st_mode)
        metadata_mode = stat.S_IMODE(os.stat(agent.directory / "metadata.json").st_mode)
        self.assertEqual(home_mode, 0o700)
        self.assertEqual(metadata_mode, 0o600)


if __name__ == "__main__":
    unittest.main()
