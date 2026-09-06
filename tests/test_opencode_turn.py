import json
import sys
from pathlib import Path

from agenty.runtime.opencode import OpenCodeRuntimeAdapter
from agenty.runtime.protocol import (
    ChannelMode,
    EvidenceLevel,
    OutputEvent,
    ProjectEnvironment,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeModelBinding,
    RuntimeModelDescriptor,
    RuntimeModelRef,
    RuntimeModelSelection,
    RuntimeSessionBinding,
    RuntimeTurnRequest,
    SessionOpenMode,
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


def model_binding(identity: RuntimeIdentity) -> RuntimeModelBinding:
    model = RuntimeModelRef(
        model_type="language",
        provider_id="provider",
        model_id="model",
    )
    return RuntimeModelBinding(
        runtime=identity,
        selection=RuntimeModelSelection(model=model, effort="high"),
        descriptor=RuntimeModelDescriptor(
            runtime=identity,
            model=model,
            supported_efforts=("low", "high"),
            evidence=EvidenceLevel.PROBE_VERIFIED,
            evidence_source="fake model catalog",
        ),
    )


def request(
    working_directory: Path,
    prompt: str = "answer briefly",
    model: RuntimeModelBinding | None = None,
):
    return RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt=prompt,
        working_directory=str(working_directory),
        model=model,
    )


def resume_request(
    identity: RuntimeIdentity,
    working_directory: Path,
) -> RuntimeTurnRequest:
    environment = ProjectEnvironment(
        environment_id="env-main",
        project_id="agenty",
        working_directory=str(working_directory),
    )
    return request(working_directory).model_copy(
        update={
            "session": RuntimeSessionBinding(
                runtime=identity,
                session_id="session-1",
                environment=environment,
                origin=SessionOpenMode.NEW,
            )
        }
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
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(str(executable))
    runner = RuntimeTurnRunner(adapter, identity)

    result = runner.run(request(working_directory))

    assert result.state is TurnState.SUCCEEDED
    assert result.session_id == "session-1"
    text_events = [
        event
        for event in result.events
        if event.name is OutputEvent.TEXT_EMITTED
    ]
    assert [event.payload["text"] for event in text_events] == ["done"]
    assert [event.sequence for event in result.events] == list(
        range(1, len(result.events) + 1)
    )
    assert all(event.raw_event is None for event in result.events)
    stream = runner.last_event_stream
    assert stream is not None
    assert len(stream.raw_events) == 3


def test_command_binds_directory_and_separates_option_like_prompt(tmp_path):
    executable, invocation_path, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(str(executable))
    turn_request = request(
        working_directory,
        prompt="--auto",
        model=model_binding(identity),
    )

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


def test_resume_uses_only_validated_session_binding(tmp_path):
    executable, invocation_path, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(str(executable))

    result = RuntimeTurnRunner(adapter, identity).run(
        resume_request(identity, working_directory)
    )
    invocation = json.loads(invocation_path.read_text())

    assert result.state is TurnState.SUCCEEDED
    assert invocation["args"][-4:] == [
        "--session",
        "session-1",
        "--",
        "answer briefly",
    ]
    assert "--continue" not in invocation["args"]
    assert "--fork" not in invocation["args"]


def test_resume_binding_for_another_runtime_is_rejected_before_start(tmp_path):
    executable, invocation_path, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    request_for_other_runtime = resume_request(
        identity.model_copy(update={"runtime_id": "other-opencode"}),
        working_directory,
    )

    result = RuntimeTurnRunner(
        OpenCodeRuntimeAdapter(str(executable)), identity
    ).run(request_for_other_runtime)

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.SESSION_ID_MISMATCH
    assert not invocation_path.exists()


def test_model_binding_for_another_runtime_is_rejected_before_start(tmp_path):
    executable, invocation_path, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    other = identity.model_copy(update={"runtime_id": "other-opencode"})
    turn_request = request(
        working_directory,
        model=model_binding(other),
    )

    result = RuntimeTurnRunner(
        OpenCodeRuntimeAdapter(str(executable)), identity
    ).run(turn_request)

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.IDENTITY_MISMATCH
    assert not invocation_path.exists()


def test_resume_rejects_runtime_output_from_another_session(tmp_path):
    executable, _, working_directory = fake_opencode(tmp_path)
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json\n"
        "print(json.dumps({"
        "'type': 'text', 'sessionID': 'session-2', "
        "'part': {'text': 'wrong session'}}))\n"
    )
    executable.chmod(0o755)
    identity = runtime(executable)

    result = RuntimeTurnRunner(
        OpenCodeRuntimeAdapter(str(executable)), identity
    ).run(resume_request(identity, working_directory))

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.INVALID_OUTPUT


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
