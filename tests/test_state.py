import multiprocessing
import sys
import tempfile
import unittest
from pathlib import Path

from agenty.state import AgentStateMachine, StateTransitionError
from agenty.store import AgentyStore, atomic_write_json


def create_checkpoint_in_process(home: str, agents_home: str, agent_id: str, index: int):
    store = AgentyStore(home, agents_home)
    agent = store.resolve_agent(agent_id)
    AgentStateMachine(agent.directory).checkpoint({"index": index})


class StateMachineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.store = AgentyStore(root / "home", root / "workers")
        self.store.initialize()
        self.store.add_runtime("mock", [sys.executable, "-c", "pass"])
        self.agent = self.store.claim("state-agent", "mock")
        self.machine = AgentStateMachine(self.agent.directory)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_and_invalid_transitions(self):
        worker = self.machine.transition("lifecycle", "WORKER", "workspace.created")
        self.assertEqual(worker["lifecycle"]["phase"], "WORKER")
        revision = worker["revision"]

        with self.assertRaises(StateTransitionError):
            self.machine.transition("lifecycle", "PROJECT", "invalid.skip")

        self.assertEqual(self.machine.load()["revision"], revision)

    def test_recovers_current_snapshot_from_event_log(self):
        checkpoint_id, expected = self.machine.checkpoint(
            {"pending_action": "continue"}, summary="recovery test"
        )
        self.machine.current_path.unlink()

        recovered = self.machine.load()

        self.assertEqual(recovered["revision"], expected["revision"])
        self.assertEqual(recovered["recovery"]["last_checkpoint"], checkpoint_id)
        self.assertTrue(self.machine.current_path.is_file())

    def test_recovers_when_current_snapshot_is_behind(self):
        original = self.machine.load()
        _, expected = self.machine.checkpoint({"value": 1})
        atomic_write_json(self.machine.current_path, original)

        recovered = self.machine.load()

        self.assertEqual(recovered["revision"], expected["revision"])

    def test_checkpoint_persists_payload(self):
        checkpoint_id, state = self.machine.checkpoint(
            {"pending_action": "review", "task": "T-1"}, summary="handoff"
        )
        checkpoint = (
            self.machine.checkpoints_dir / f"{checkpoint_id}.json"
        ).read_text(encoding="utf-8")

        self.assertIn('"task": "T-1"', checkpoint)
        self.assertEqual(state["recovery"]["pending_action"], "review")

    def test_task_context_is_persisted_across_terminal_transition(self):
        active = self.machine.start_task(
            "Inspect project", task_id="task_1", session_id="session_1"
        )
        completed = self.machine.finish_task("COMPLETED")

        self.assertEqual(active["task"]["status"], "ACTIVE")
        self.assertEqual(completed["task"]["status"], "COMPLETED")
        self.assertEqual(completed["task"]["task_id"], "task_1")
        self.assertEqual(completed["task"]["session_id"], "session_1")

    def test_concurrent_checkpoints_have_unique_contiguous_revisions(self):
        context = multiprocessing.get_context("spawn")
        processes = [
            context.Process(
                target=create_checkpoint_in_process,
                args=(
                    str(self.store.home),
                    str(self.store.agents_home),
                    self.agent.agent_id,
                    index,
                ),
            )
            for index in range(5)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
            self.assertEqual(process.exitcode, 0)

        revisions = [event["revision"] for event in self.machine.history()]
        self.assertEqual(revisions, list(range(6)))


if __name__ == "__main__":
    unittest.main()
