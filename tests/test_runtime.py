import sys
import tempfile
import unittest
from pathlib import Path

from agenty.runtime import launch_agent
from agenty.state import AgentStateMachine
from agenty.store import AgentyStore


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.store = AgentyStore(root / "home", root / "workers")
        self.store.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dry_run_does_not_change_execution_state(self):
        self.store.add_runtime("mock", [sys.executable, "-c", "pass"])
        agent = self.store.claim("dry-agent", "mock")
        before = AgentStateMachine(agent.directory).load()

        result = launch_agent(self.store, agent.agent_id, dry_run=True)

        after = AgentStateMachine(agent.directory).load()
        self.assertTrue(result["dry_run"])
        self.assertEqual(before["revision"], after["revision"])
        self.assertEqual(after["execution"]["status"], "IDLE")

    def test_successful_runtime_returns_to_idle(self):
        self.store.add_runtime("success", [sys.executable, "-c", "print('ok')"])
        agent = self.store.claim("success-agent", "success")

        result = launch_agent(self.store, agent.agent_id)

        state = AgentStateMachine(agent.directory).load()
        self.assertEqual(result["return_code"], 0)
        self.assertEqual(state["execution"]["status"], "IDLE")
        self.assertIsNone(state["execution"]["runtime_pid"])

    def test_failed_runtime_records_failed_state(self):
        self.store.add_runtime("failure", [sys.executable, "-c", "raise SystemExit(7)"])
        agent = self.store.claim("failure-agent", "failure")

        result = launch_agent(self.store, agent.agent_id)

        state = AgentStateMachine(agent.directory).load()
        self.assertEqual(result["return_code"], 7)
        self.assertEqual(state["execution"]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
