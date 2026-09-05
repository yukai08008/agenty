import json
import sys
from pathlib import Path

from agenty.runtime.opencode import OpenCodeRuntimeAdapter
from agenty.runtime.protocol import (
    ChannelMode,
    OutputEvent,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeTurnRequest,
    TurnState,
)
from agenty.runtime.runner import RuntimeTurnRunner


def fake_opencode(
    tmp_path: Path,
    *,
    mode: str = "success",
    exit_code: int = 0,
    delay: float = 0,
) -> tuple[Path, Path, Path]:
    executable = tmp_path / "opencode"
    invocation = tmp_path / "invocation.json"
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    events = [
        {"type": "step_start", "sessionID": "session-1", "part": {}},
        {
            "type": "text",
            "sessionID": "session-1",
            "part": {"text": "done"},
        },
        {"type": "step_finish", "sessionID": "session-1", "part": {}},
    ]
    if mode == "error":
        events = [
            {
                "type": "error",
                "sessionID": "session-1",
                "error": {
                    "name": "APIError",
                    "data": {
                        "message": "model failed",
                        "statusCode": 429,
                        "isRetryable": True,
                    },
                },
            }
        ]
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys, time\n"
        f"INVOCATION = pathlib.Path({str(invocation)!r})\n"
        "INVOCATION.write_text(json.dumps({"
        "'args': sys.argv[1:], 'cwd': os.getcwd()}))\n"
        f"time.sleep({delay!r})\n"
        + (
            "print('not-json')\n"
            if mode == "malformed"
            else "EVENTS = " + repr(events) + "\n"
            "for event in EVENTS:\n"
            "    print(json.dumps(event), flush=True)\n"
        )
        + f"raise SystemExit({exit_code})\n"
    )
    executable.chmod(0o755)
    return executable, invocation, working_directory


def runtime(executable: Path) -> RuntimeIdentity:
    return RuntimeIdentity(
        runtime_id="local-opencode",
        runtime_kind="opencode",
        runtime_version="1.18.26",
        executable=str(executable),
        channel=ChannelMode.TRANSIENT_PROCESS,
    )


def request(working_directory: Path, prompt: str = "answer briefly"):
    return RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt=prompt,
        working_directory=str(working_directory),
        model="provider/model",
        effort="high",
    )


def run_turn(executable: Path, working_directory: Path, timeout: float = 5):
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(
        str(executable),
        timeout_seconds=timeout,
    )
    return RuntimeTurnRunner(adapter, identity).run(request(working_directory))


def test_fake_opencode_drives_successful_session_bound_turn(tmp_path):
    executable, _, working_directory = fake_opencode(tmp_path)

    result = run_turn(executable, working_directory)

    assert result.state is TurnState.SUCCEEDED
    assert result.session_id == "session-1"
    text_events = [
        event
        for event in result.events
        if event.name is OutputEvent.TEXT_EMITTED
    ]
    assert [event.payload["text"] for event in text_events] == ["done"]


def test_command_binds_directory_and_separates_option_like_prompt(tmp_path):
    executable, invocation_path, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(str(executable))
    turn_request = request(working_directory, prompt="--auto")

    result = RuntimeTurnRunner(adapter, identity).run(turn_request)
    invocation = json.loads(invocation_path.read_text())

    assert result.state is TurnState.SUCCEEDED
    assert invocation["cwd"] == str(working_directory)
    assert invocation["args"] == [
        "run",
        "--format",
        "json",
        "--dir",
        str(working_directory),
        "--model",
        "provider/model",
        "--variant",
        "high",
        "--",
        "--auto",
    ]
    separator = invocation["args"].index("--")
    assert "--auto" not in invocation["args"][:separator]
    assert "--session" not in invocation["args"]
    assert "--continue" not in invocation["args"]
    assert "--fork" not in invocation["args"]


def test_runtime_error_event_fails_turn(tmp_path):
    executable, _, working_directory = fake_opencode(tmp_path, mode="error")

    result = run_turn(executable, working_directory)

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.TURN_FAILED
    assert result.failure.details == {
        "error_type": "APIError",
        "message": "model failed",
        "status_code": 429,
        "retryable": True,
    }
    assert any(
        event.name is OutputEvent.RUNTIME_ERROR_EMITTED
        for event in result.events
    )


def test_tool_error_is_normalized_as_tool_failed(tmp_path):
    executable, _, working_directory = fake_opencode(tmp_path)
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json\n"
        "print(json.dumps({"
        "'type': 'tool_use', 'sessionID': 'session-1', "
        "'part': {'tool': 'write', 'state': {'status': 'error'}}}))\n"
    )
    executable.chmod(0o755)

    result = run_turn(executable, working_directory)

    assert result.state is TurnState.SUCCEEDED
    tool_events = [
        event for event in result.events if event.name is OutputEvent.TOOL_FAILED
    ]
    assert len(tool_events) == 1
    assert tool_events[0].payload == {"tool": "write"}


def test_malformed_json_fails_turn(tmp_path):
    executable, _, working_directory = fake_opencode(
        tmp_path,
        mode="malformed",
    )

    result = run_turn(executable, working_directory)

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.INVALID_OUTPUT


def test_nonzero_exit_fails_turn_even_after_valid_output(tmp_path):
    executable, _, working_directory = fake_opencode(tmp_path, exit_code=7)

    result = run_turn(executable, working_directory)

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.TURN_FAILED
    assert result.failure.details["returncode"] == 7


def test_timeout_terminates_process_and_times_out_turn(tmp_path):
    executable, _, working_directory = fake_opencode(tmp_path, delay=1)

    result = run_turn(executable, working_directory, timeout=0.01)

    assert result.state is TurnState.TIMED_OUT
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.TURN_TIMEOUT


def test_missing_working_directory_rejects_turn_before_process_start(tmp_path):
    executable, invocation_path, _ = fake_opencode(tmp_path)
    missing = tmp_path / "missing-project"

    result = run_turn(executable, missing)

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.TURN_REJECTED
    assert not invocation_path.exists()
