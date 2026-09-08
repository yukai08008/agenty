import json
import sys
import threading
from pathlib import Path

from agenty.runtime.adapters import RuntimeTurnControl
from agenty.runtime.opencode import OpenCodeRuntimeAdapter
from agenty.runtime.protocol import (
    INTERACTION_AUTO_APPROVE_CAPABILITY,
    CapabilityRecord,
    CapabilitySupport,
    ChannelMode,
    EvidenceLevel,
    InteractionEvent,
    InteractionPolicyMode,
    OutputEvent,
    ProjectEnvironment,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeInteractionPolicy,
    RuntimeModelBinding,
    RuntimeModelDescriptor,
    RuntimeModelRef,
    RuntimeModelSelection,
    RuntimeSessionBinding,
    RuntimeTurnRequest,
    SessionOpenMode,
    TurnEvent,
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
        {
            "type": "step_finish",
            "sessionID": "session-1",
            "part": {
                "tokens": {
                    "input": 10,
                    "output": 4,
                    "reasoning": 2,
                    "cache": {"read": 3, "write": 1},
                },
                "cost": 0.0025,
            },
        },
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
        "if sys.argv[1:3] == ['debug', 'config']:\n"
        "    config = json.loads(os.environ.get('OPENCODE_CONFIG_CONTENT', '{}'))\n"
        "    base = {'mcp': {'test-mcp': {'type': 'local', "
        "'command': ['false'], 'enabled': True}}}\n"
        "    base.update(config)\n"
        "    if 'mcp' in config:\n"
        "        base['mcp'] = {**base['mcp'], **config['mcp']}\n"
        "    print(json.dumps(base))\n"
        "    raise SystemExit(0)\n"
        "INVOCATION.write_text(json.dumps({"
        "'args': sys.argv[1:], 'cwd': os.getcwd(), "
        "'disable_project_config': "
        "os.environ.get('OPENCODE_DISABLE_PROJECT_CONFIG'), "
        "'config_content': os.environ.get('OPENCODE_CONFIG_CONTENT')}))\n"
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
    interaction: RuntimeInteractionPolicy | None = None,
):
    return RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt=prompt,
        working_directory=str(working_directory),
        model=model,
        interaction=interaction or RuntimeInteractionPolicy(),
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


def inline_fake_opencode(events: str) -> str:
    return (
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "if sys.argv[1:3] == ['debug', 'config']:\n"
        "    config = json.loads(os.environ.get('OPENCODE_CONFIG_CONTENT', '{}'))\n"
        "    print(json.dumps(config))\n"
        "    raise SystemExit(0)\n"
        f"{events}\n"
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
    assert result.output_text == "done"
    assert result.usage.total_tokens == 20
    assert str(result.usage.cost) == "0.0025"
    assert result.event_log.normalized_event_count == len(result.events)
    assert result.event_log.raw_event_count == 3


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
        "--pure",
        "--agent",
        "agenty-deny-by-default",
        "--",
        "--auto",
    ]
    separator = invocation["args"].index("--")
    assert "--auto" not in invocation["args"][:separator]
    assert "--session" not in invocation["args"]
    assert "--continue" not in invocation["args"]
    assert "--fork" not in invocation["args"]


def test_explicit_auto_approve_maps_to_runtime_auto_and_is_audited(tmp_path):
    executable, invocation_path, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(str(executable))
    capability = (
        CapabilityRecord(
            capability=INTERACTION_AUTO_APPROVE_CAPABILITY,
            runtime=identity,
            support=CapabilitySupport.SUPPORTED,
            evidence=EvidenceLevel.INTEGRATION_VERIFIED,
            evidence_source="test integration",
        ),
    )
    turn_request = request(
        working_directory,
        interaction=RuntimeInteractionPolicy(
            mode=InteractionPolicyMode.AUTO_APPROVE
        ),
    )

    result = RuntimeTurnRunner(adapter, identity, capability).run(turn_request)
    invocation = json.loads(invocation_path.read_text())

    separator = invocation["args"].index("--")
    assert invocation["args"][separator - 1] == "--auto"
    assert "--agent" not in invocation["args"][:separator]
    assert "--pure" not in invocation["args"][:separator]
    assert INTERACTION_AUTO_APPROVE_CAPABILITY in {
        record.capability for record in capability
    }
    policies = [
        event
        for event in result.events
        if event.name is InteractionEvent.INTERACTION_POLICY_APPLIED
    ]
    assert policies[0].payload["policy"]["mode"] == "auto_approve"


def test_deny_by_default_injects_highest_priority_permission_policy(tmp_path):
    executable, invocation_path, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(str(executable))
    turn_request = request(working_directory)

    environment = adapter._turn_environment(
        identity,
        turn_request,
        RuntimeTurnControl(),
    )
    config = json.loads(environment["OPENCODE_CONFIG_CONTENT"])
    result = RuntimeTurnRunner(adapter, identity).run(turn_request)
    invocation = json.loads(invocation_path.read_text())

    assert result.state is TurnState.SUCCEEDED
    assert config["agent"]["agenty-deny-by-default"]["permission"] == "deny"
    assert config["mcp"]["test-mcp"]["enabled"] is False
    assert invocation["disable_project_config"] == "1"
    separator = invocation["args"].index("--")
    assert invocation["args"][:separator][-3:] == [
        "--pure",
        "--agent",
        "agenty-deny-by-default",
    ]


def test_invalid_inline_config_fails_closed_before_process_start(
    monkeypatch,
    tmp_path,
):
    executable, invocation_path, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", "not-json")

    result = RuntimeTurnRunner(
        OpenCodeRuntimeAdapter(str(executable)), identity
    ).run(request(working_directory))

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.TURN_REJECTED
    assert not invocation_path.exists()


def test_interrupt_reclaims_active_process(monkeypatch, tmp_path):
    executable, _, _ = fake_opencode(tmp_path)
    adapter = OpenCodeRuntimeAdapter(str(executable))

    class InterruptedProcess:
        def communicate(self, timeout):
            raise KeyboardInterrupt

        def poll(self):
            return None

    stopped = []
    monkeypatch.setattr(
        adapter,
        "_terminate_process",
        lambda process: stopped.append(process) or ("", ""),
    )

    try:
        adapter._wait_for_process(InterruptedProcess(), RuntimeTurnControl())
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("interrupt was not propagated")

    assert len(stopped) == 1


def test_closing_generator_after_acceptance_reclaims_process(monkeypatch, tmp_path):
    executable, _, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(str(executable), timeout_seconds=5)
    stopped = []

    class HangingProcess:
        def poll(self):
            return None

    process = HangingProcess()
    monkeypatch.setattr(
        "agenty.runtime.opencode.subprocess.Popen",
        lambda *args, **kwargs: process,
    )
    monkeypatch.setattr(
        adapter,
        "_terminate_process",
        lambda active: stopped.append(active) or ("", ""),
    )
    monkeypatch.setattr(
        adapter,
        "_resolved_config",
        lambda *args: {
            "agent": {
                "agenty-deny-by-default": {"permission": {"*": "deny"}}
            },
            "mcp": {},
        },
    )
    events = adapter.iter_turn_events(
        identity,
        request(working_directory),
        RuntimeTurnControl(),
    )

    assert next(events).name is TurnEvent.TURN_ACCEPTED
    events.close()

    assert stopped == [process]


def test_ambient_override_of_deny_agent_fails_closed(monkeypatch, tmp_path):
    executable, invocation_path, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(str(executable))
    resolved = iter(
        (
            {"mcp": {}},
            {
                "agent": {
                    "agenty-deny-by-default": {"permission": {"*": "allow"}}
                },
                "mcp": {},
            },
        )
    )
    monkeypatch.setattr(
        adapter,
        "_resolved_config",
        lambda *args: next(resolved),
    )

    result = RuntimeTurnRunner(adapter, identity).run(request(working_directory))

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.TURN_REJECTED
    assert not invocation_path.exists()


def test_safe_config_probe_uses_process_group_and_bounded_timeout(
    monkeypatch,
    tmp_path,
):
    executable, _, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(str(executable), timeout_seconds=5)
    observed = {}

    class FinishedProcess:
        returncode = 0

    process = FinishedProcess()

    def fake_popen(command, **kwargs):
        observed.update(command=command, **kwargs)
        return process

    monkeypatch.setattr("agenty.runtime.opencode.subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        adapter,
        "_wait_for_process",
        lambda active, control, **kwargs: (
            observed.update(wait=kwargs) or ('{"mcp": {}}', "")
        ),
    )

    adapter._resolved_config(
        identity,
        request(working_directory),
        {},
        RuntimeTurnControl(),
    )

    assert observed["start_new_session"] is True
    assert observed["wait"]["timeout_seconds"] == 5


def test_ask_is_rejected_before_process_start_for_transient_channel(tmp_path):
    executable, invocation_path, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(str(executable))
    turn_request = request(
        working_directory,
        interaction=RuntimeInteractionPolicy(mode=InteractionPolicyMode.ASK),
    )

    result = RuntimeTurnRunner(
        adapter,
        identity,
        (),
    ).run(turn_request)

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.INTERACTION_UNSUPPORTED
    assert not invocation_path.exists()


def test_cancel_reclaims_process_and_reaches_cancelled(tmp_path):
    executable, _, working_directory = fake_opencode(tmp_path, delay=2)
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(str(executable), timeout_seconds=5)
    runner = RuntimeTurnRunner(adapter, identity)
    outcome = {}

    thread = threading.Thread(
        target=lambda: outcome.update(result=runner.run(request(working_directory)))
    )
    thread.start()
    for _ in range(100):
        machine = runner._machine
        if machine is not None and machine.state is TurnState.RUNNING:
            break
        threading.Event().wait(0.01)
    runner.cancel("user:andy")
    thread.join(timeout=2)

    result = outcome["result"]
    assert result.state is TurnState.CANCELLED
    assert any(
        event.name is InteractionEvent.TURN_CANCEL_REQUESTED
        for event in result.events
    )


def test_resume_uses_only_validated_session_binding(tmp_path):
    executable, invocation_path, working_directory = fake_opencode(tmp_path)
    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(str(executable))

    result = RuntimeTurnRunner(adapter, identity).run(
        resume_request(identity, working_directory)
    )
    invocation = json.loads(invocation_path.read_text())

    assert result.state is TurnState.SUCCEEDED
    session_index = invocation["args"].index("--session")
    assert invocation["args"][session_index : session_index + 2] == [
        "--session",
        "session-1",
    ]
    assert invocation["args"][-2:] == [
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
        inline_fake_opencode(
            "print(json.dumps({'type': 'text', 'sessionID': 'session-2', "
            "'part': {'text': 'wrong session'}}))"
        )
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
    assert result.failure.code is RuntimeFailureCode.RATE_LIMITED
    assert result.failure.retryable is True
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
        inline_fake_opencode(
            "print(json.dumps({'type': 'tool_use', 'sessionID': 'session-1', "
            "'part': {'tool': 'write', 'state': {'status': 'error'}}}))"
        )
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
    assert result.failure.details == {"line_number": 1}
    raw_records = [
        json.loads(line)
        for line in Path(result.event_log.raw_path).read_text().splitlines()
    ]
    assert raw_records[-1]["data"] == "not-json"
    assert raw_records[-1]["source_reference"] == "adapter-invalid-output"


def test_invalid_usage_fails_turn_and_preserves_raw_evidence(tmp_path):
    executable, _, working_directory = fake_opencode(tmp_path)
    executable.write_text(
        inline_fake_opencode(
            "print(json.dumps({'type': 'step_finish', 'sessionID': 'session-1', "
            "'part': {'tokens': {'input': -1}}}))"
        )
    )
    executable.chmod(0o755)

    result = run_turn(executable, working_directory)

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.INVALID_OUTPUT
    assert result.failure.details == {
        "line_number": 1,
        "field": "tokens.input",
    }
    raw_records = [
        json.loads(line)
        for line in Path(result.event_log.raw_path).read_text().splitlines()
    ]
    assert raw_records[-1]["data"]["part"]["tokens"]["input"] == -1


def test_nonzero_exit_fails_turn_even_after_valid_output(tmp_path):
    executable, _, working_directory = fake_opencode(tmp_path, exit_code=7)

    result = run_turn(executable, working_directory)

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.RUNTIME_CRASH
    assert result.failure.retryable is False
    assert result.failure.details["returncode"] == 7


def test_timeout_terminates_process_and_times_out_turn(tmp_path):
    executable, _, working_directory = fake_opencode(tmp_path, delay=1)

    identity = runtime(executable)
    adapter = OpenCodeRuntimeAdapter(
        str(executable),
        timeout_seconds=0.01,
    )
    result = RuntimeTurnRunner(
        adapter,
        identity,
        (
            CapabilityRecord(
                capability=INTERACTION_AUTO_APPROVE_CAPABILITY,
                runtime=identity,
                support=CapabilitySupport.SUPPORTED,
                evidence=EvidenceLevel.INTEGRATION_VERIFIED,
                evidence_source="test integration",
            ),
        ),
    ).run(
        request(
            working_directory,
            interaction=RuntimeInteractionPolicy(
                mode=InteractionPolicyMode.AUTO_APPROVE
            ),
        )
    )

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
