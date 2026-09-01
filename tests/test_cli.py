import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliPocTests(unittest.TestCase):
    def test_cli_runs_claim_worker_snapshot_and_migration_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env = os.environ.copy()
            env["AGENTY_HOME"] = str(root / "home")
            env["AGENTY_AGENTS_HOME"] = str(root / "workers")

            self.assert_ok(self.run_cli(env, "init"))
            self.assert_ok(
                self.run_cli(
                    env,
                    "runtime",
                    "add",
                    "mock",
                    sys.executable,
                    "-c",
                    "pass",
                )
            )
            self.assert_ok(self.run_cli(env, "claim", "cli-agent", "--runtime", "mock"))
            self.assert_ok(self.run_cli(env, "claim", "second-agent", "--runtime", "mock"))
            listed = self.run_cli(env, "list")
            self.assert_ok(listed)
            self.assertIn("cli-agent", listed.stdout)
            self.assertIn("second-agent", listed.stdout)

            self.assert_ok(self.run_cli(env, "workspace", "create", "cli-agent"))
            project_file = root / "workers" / "cli-agent" / "workspace" / "README.md"
            project_file.write_text("CLI flow", encoding="utf-8")
            self.assert_ok(self.run_cli(env, "snapshot", "cli-agent"))
            snapshot_state = self.run_cli(env, "show", "cli-agent")
            self.assert_ok(snapshot_state)
            self.assertIn("COMPLETED", snapshot_state.stdout)
            self.assert_ok(
                self.run_cli(
                    env,
                    "checkpoint",
                    "cli-agent",
                    "--summary",
                    "ready",
                    "--pending-action",
                    "migrate",
                )
            )
            shown = self.run_cli(env, "show", "cli-agent")
            self.assert_ok(shown)
            self.assertIn("WORKER", shown.stdout)
            self.assert_ok(self.run_cli(env, "start", "cli-agent", "--dry-run"))

            target = root / "project"
            self.assert_ok(
                self.run_cli(env, "migrate", "cli-agent", str(target), "--init-git")
            )
            final = self.run_cli(env, "show", "cli-agent")
            self.assert_ok(final)
            self.assertIn("PROJECT", final.stdout)
            self.assert_ok(self.run_cli(env, "doctor", "cli-agent"))
            self.assertTrue((target / ".git").is_dir())
            self.assertTrue((root / "workers" / "cli-agent").is_dir())

    @staticmethod
    def run_cli(env, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "agenty.cli", *arguments],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def assert_ok(self, result):
        self.assertEqual(
            result.returncode,
            0,
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
