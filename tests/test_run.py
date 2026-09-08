from pathlib import Path

from agenty import run
from agenty.runtime.protocol import (
    INTERACTION_AUTO_APPROVE_CAPABILITY,
    CapabilityRecord,
    CapabilitySupport,
    ChannelMode,
    EvidenceLevel,
    InteractionPolicyMode,
    OutputEvent,
    RuntimeEvent,
    RuntimeIdentity,
    TurnEvent,
    TurnState,
)


class FakeOpenCodeAdapter:
    def __init__(self, executable="opencode", timeout_seconds=300):
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.seen_request = None

    @property
    def identity(self):
        return RuntimeIdentity(
            runtime_id="local-opencode",
            runtime_kind="opencode",
            channel=ChannelMode.TRANSIENT_PROCESS,
        )

    def detect(self):
        return self.identity.model_copy(
            update={
                "runtime_version": run.OPENCODE_RUNTIME_VERSION,
                "executable": "/usr/local/bin/opencode",
            }
        )

    def probe_capabilities(self, runtime):
        return (
            CapabilityRecord(
                capability=INTERACTION_AUTO_APPROVE_CAPABILITY,
                runtime=runtime,
                support=CapabilitySupport.SUPPORTED,
                evidence=EvidenceLevel.INTEGRATION_VERIFIED,
                evidence_source="fake adapter integration",
            ),
        )

    def iter_turn_events(self, runtime, request, control):
        self.seen_request = request
        yield RuntimeEvent(
            name=TurnEvent.TURN_ACCEPTED,
            runtime=runtime,
            correlation_id=request.correlation_id,
            turn_id=request.turn_id,
        )
        yield RuntimeEvent(
            name=OutputEvent.TEXT_EMITTED,
            runtime=runtime,
            correlation_id=request.correlation_id,
            turn_id=request.turn_id,
            session_id="session-1",
            payload={"text": "task complete"},
        )
        yield RuntimeEvent(
            name=TurnEvent.TURN_SUCCEEDED,
            runtime=runtime,
            correlation_id=request.correlation_id,
            turn_id=request.turn_id,
            session_id="session-1",
        )

    def reply_approval(self, decision):
        raise AssertionError("approval reply is not expected")


def test_run_opencode_task_uses_exact_runtime_and_safe_default(monkeypatch, tmp_path):
    adapter = FakeOpenCodeAdapter()
    monkeypatch.setattr(run, "OpenCodeRuntimeAdapter", lambda **kwargs: adapter)

    result = run.run_opencode_task("inspect this project", working_directory=tmp_path)

    assert result.state is TurnState.SUCCEEDED
    assert result.runtime.runtime_version == run.OPENCODE_RUNTIME_VERSION
    assert result.output_text == "task complete"
    assert adapter.seen_request.working_directory == str(tmp_path.resolve())
    assert (
        adapter.seen_request.interaction.mode
        is InteractionPolicyMode.DENY_BY_DEFAULT
    )


def test_run_opencode_task_requires_explicit_auto_approve(monkeypatch, tmp_path):
    adapter = FakeOpenCodeAdapter()
    monkeypatch.setattr(run, "OpenCodeRuntimeAdapter", lambda **kwargs: adapter)

    run.run_opencode_task(
        "inspect this project",
        working_directory=tmp_path,
        auto_approve=True,
    )

    assert (
        adapter.seen_request.interaction.mode
        is InteractionPolicyMode.AUTO_APPROVE
    )


def test_run_opencode_task_rejects_wrong_runtime_version(monkeypatch, tmp_path):
    class WrongVersionAdapter(FakeOpenCodeAdapter):
        def detect(self):
            return self.identity.model_copy(
                update={
                    "runtime_version": "1.18.25",
                    "executable": "/usr/local/bin/opencode",
                }
            )

    monkeypatch.setattr(
        run,
        "OpenCodeRuntimeAdapter",
        lambda **kwargs: WrongVersionAdapter(),
    )

    try:
        run.run_opencode_task("inspect", working_directory=Path(tmp_path))
    except run.AgentyRunError as exc:
        assert exc.failure.code.value == "runtime_identity_mismatch"
    else:
        raise AssertionError("wrong runtime version was accepted")


def test_run_opencode_task_rejects_blank_task_before_runtime_probe(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        run,
        "OpenCodeRuntimeAdapter",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("runtime should not be probed")
        ),
    )

    try:
        run.run_opencode_task("   ", working_directory=tmp_path)
    except run.AgentyRunError as exc:
        assert exc.failure.code.value == "turn_rejected"
    else:
        raise AssertionError("blank task was accepted")


def test_run_opencode_task_rejects_invalid_timeout_before_runtime_probe(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        run,
        "OpenCodeRuntimeAdapter",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("runtime should not be probed")
        ),
    )

    try:
        run.run_opencode_task(
            "inspect",
            working_directory=tmp_path,
            timeout_seconds=float("nan"),
        )
    except run.AgentyRunError as exc:
        assert exc.failure.code.value == "turn_rejected"
    else:
        raise AssertionError("invalid timeout was accepted")
