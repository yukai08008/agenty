import json
from types import SimpleNamespace

import pytest

from agenty import cli
from agenty.run import AgentyRunError
from agenty.runtime.protocol import (
    RuntimeFailure,
    RuntimeFailureCode,
    TurnState,
)


class FakeResult(SimpleNamespace):
    def model_dump_json(self):
        return json.dumps({"state": self.state.value, "output_text": self.output_text})


def test_run_command_passes_explicit_execution_policy(monkeypatch, tmp_path, capsys):
    observed = {}

    def fake_run(prompt, **kwargs):
        observed.update(prompt=prompt, **kwargs)
        return FakeResult(state=TurnState.SUCCEEDED, output_text="ok")

    monkeypatch.setattr(cli, "run_opencode_task", fake_run)

    exit_code = cli.main(
        [
            "run",
            "inspect",
            "disk",
            "-C",
            str(tmp_path),
            "--auto-approve",
            "--timeout",
            "12",
            "--json",
        ]
    )

    assert exit_code == 0
    assert observed == {
        "prompt": "inspect disk",
        "working_directory": str(tmp_path),
        "auto_approve": True,
        "timeout_seconds": 12.0,
        "executable": "opencode",
    }
    assert json.loads(capsys.readouterr().out) == {
        "state": "succeeded",
        "output_text": "ok",
    }


def test_run_command_returns_nonzero_for_failed_turn(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "run_opencode_task",
        lambda *args, **kwargs: FakeResult(
            state=TurnState.FAILED,
            output_text="",
        ),
    )

    exit_code = cli.main(["run", "inspect", "--json"])

    assert exit_code == 1
    assert json.loads(capsys.readouterr().out)["state"] == "failed"


def test_run_command_returns_two_when_runtime_selection_fails(
    monkeypatch,
    capsys,
):
    failure = RuntimeFailure(
        code=RuntimeFailureCode.UNSUPPORTED_VERSION,
        message="unsupported OpenCode version",
    )

    def fail_selection(*args, **kwargs):
        raise AgentyRunError(failure)

    monkeypatch.setattr(cli, "run_opencode_task", fail_selection)

    exit_code = cli.main(["run", "inspect", "--json"])

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out) == failure.model_dump(mode="json")


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "0", "-1"])
def test_run_command_rejects_non_positive_or_non_finite_timeout(value):
    with pytest.raises(SystemExit) as exc:
        cli.main(["run", "inspect", "--timeout", value])

    assert exc.value.code == 2


def test_run_command_returns_130_on_interrupt(monkeypatch, capsys):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_opencode_task", interrupt)

    assert cli.main(["run", "inspect"]) == 130
    assert "OpenCode was stopped" in capsys.readouterr().out


def test_json_run_command_returns_json_on_interrupt(monkeypatch, capsys):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_opencode_task", interrupt)

    assert cli.main(["run", "inspect", "--json"]) == 130
    assert json.loads(capsys.readouterr().out) == {
        "state": "interrupted",
        "exit_code": 130,
    }
