import pytest

from agenty.runtime.protocol import (
    INTERACTION_APPROVAL_CAPABILITY,
    ApprovalOutcome,
    CapabilityRecord,
    CapabilitySupport,
    ChannelMode,
    EvidenceLevel,
    InteractionEvent,
    InteractionPolicyMode,
    RuntimeApprovalRequest,
    RuntimeEvent,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeInteractionPolicy,
    RuntimeTurnRequest,
    TurnEvent,
    TurnState,
)
from agenty.runtime.runner import RuntimeTurnRunner


def test_invalid_adapter_lifecycle_becomes_invalid_output_failure():
    runtime = RuntimeIdentity(
        runtime_id="local-fake",
        runtime_kind="fake",
        runtime_version="1.2.3",
        channel=ChannelMode.TRANSIENT_PROCESS,
    )
    request = RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt="hello",
        working_directory="/tmp/project",
    )

    class InvalidLifecycleAdapter:
        def iter_turn_events(self, runtime, request, control):
            yield RuntimeEvent(
                name=TurnEvent.TURN_SUCCEEDED,
                runtime=runtime,
                correlation_id=request.correlation_id,
                turn_id=request.turn_id,
            )

    runner = RuntimeTurnRunner(InvalidLifecycleAdapter(), runtime)

    result = runner.run(request)

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.INVALID_OUTPUT
    stream = runner.last_event_stream
    assert stream is not None
    assert [event.sequence for event in stream.events] == [1, 2, 3, 4]
    assert TurnEvent.TURN_SUCCEEDED not in {event.name for event in stream.events}


def test_runner_pauses_for_ask_and_resumes_with_matching_decision():
    runtime = RuntimeIdentity(
        runtime_id="local-fake",
        runtime_kind="fake",
        runtime_version="1.2.3",
        channel=ChannelMode.MANAGED_SERVER,
    )
    request = RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt="hello",
        working_directory="/tmp/project",
        interaction=RuntimeInteractionPolicy(mode=InteractionPolicyMode.ASK),
    )

    class ApprovalAdapter:
        def __init__(self):
            self.decision = None

        def iter_turn_events(self, runtime, request, control):
            yield RuntimeEvent(
                name=TurnEvent.TURN_ACCEPTED,
                runtime=runtime,
                correlation_id=request.correlation_id,
                turn_id=request.turn_id,
            )
            yield RuntimeEvent(
                name=TurnEvent.TURN_WAITING_FOR_APPROVAL,
                runtime=runtime,
                correlation_id=request.correlation_id,
                turn_id=request.turn_id,
                payload={
                    "request": RuntimeApprovalRequest(
                        request_id="approval-1",
                        permission="write",
                    )
                },
            )
            assert self.decision is not None
            yield RuntimeEvent(
                name=TurnEvent.TURN_APPROVAL_RESOLVED,
                runtime=runtime,
                correlation_id=request.correlation_id,
                turn_id=request.turn_id,
            )
            yield RuntimeEvent(
                name=TurnEvent.TURN_SUCCEEDED,
                runtime=runtime,
                correlation_id=request.correlation_id,
                turn_id=request.turn_id,
            )

        def reply_approval(self, decision):
            self.decision = decision

    adapter = ApprovalAdapter()
    capability = CapabilityRecord(
        capability=INTERACTION_APPROVAL_CAPABILITY,
        runtime=runtime,
        support=CapabilitySupport.SUPPORTED,
        evidence=EvidenceLevel.INTEGRATION_VERIFIED,
        evidence_source="test integration",
    )
    runner = RuntimeTurnRunner(adapter, runtime, (capability,))

    import threading

    outcome = {}

    def execute():
        outcome["result"] = runner.run(request)

    thread = threading.Thread(target=execute)
    thread.start()
    for _ in range(100):
        interaction = runner.active_interaction
        if interaction is not None and interaction.pending_request is not None:
            break
        threading.Event().wait(0.01)
    runner.reply_approval(
        "approval-1",
        ApprovalOutcome.APPROVED,
        "user:andy",
    )
    thread.join(timeout=2)

    result = outcome["result"]
    assert result.state is TurnState.SUCCEEDED
    assert adapter.decision is not None
    assert adapter.decision.actor == "user:andy"
    assert [
        event.name
        for event in result.events
        if isinstance(event.name, InteractionEvent)
    ] == [
        InteractionEvent.INTERACTION_POLICY_APPLIED,
        InteractionEvent.APPROVAL_REQUESTED,
        InteractionEvent.APPROVAL_DECIDED,
    ]


def test_approval_timeout_reaches_timed_out_terminal_state():
    runtime = RuntimeIdentity(
        runtime_id="local-fake",
        runtime_kind="fake",
        runtime_version="1.2.3",
        channel=ChannelMode.MANAGED_SERVER,
    )
    request = RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt="hello",
        working_directory="/tmp/project",
        interaction=RuntimeInteractionPolicy(mode=InteractionPolicyMode.ASK),
    )

    class WaitingAdapter:
        def iter_turn_events(self, runtime, request, control):
            yield RuntimeEvent(
                name=TurnEvent.TURN_ACCEPTED,
                runtime=runtime,
                correlation_id=request.correlation_id,
                turn_id=request.turn_id,
            )
            yield RuntimeEvent(
                name=TurnEvent.TURN_WAITING_FOR_APPROVAL,
                runtime=runtime,
                correlation_id=request.correlation_id,
                turn_id=request.turn_id,
                payload={
                    "request": {
                        "request_id": "approval-1",
                        "permission": "write",
                    }
                },
            )

        def reply_approval(self, decision):
            raise AssertionError("approval should time out")

    capability = CapabilityRecord(
        capability=INTERACTION_APPROVAL_CAPABILITY,
        runtime=runtime,
        support=CapabilitySupport.SUPPORTED,
        evidence=EvidenceLevel.INTEGRATION_VERIFIED,
        evidence_source="test integration",
    )
    result = RuntimeTurnRunner(
        WaitingAdapter(),
        runtime,
        (capability,),
        approval_timeout_seconds=0.01,
    ).run(request)

    assert result.state is TurnState.TIMED_OUT
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.TURN_TIMEOUT


def test_failed_approval_delivery_does_not_record_false_decision_or_deadlock():
    import threading

    from agenty.runtime.adapters import RuntimeTurnAdapterError
    from agenty.runtime.interaction import InteractionState
    from agenty.runtime.protocol import RuntimeFailure

    runtime = RuntimeIdentity(
        runtime_id="local-fake",
        runtime_kind="fake",
        runtime_version="1.2.3",
        channel=ChannelMode.MANAGED_SERVER,
    )
    request = RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt="hello",
        working_directory="/tmp/project",
        interaction=RuntimeInteractionPolicy(mode=InteractionPolicyMode.ASK),
    )

    class FailingReplyAdapter:
        def iter_turn_events(self, runtime, request, control):
            yield RuntimeEvent(
                name=TurnEvent.TURN_ACCEPTED,
                runtime=runtime,
                correlation_id=request.correlation_id,
                turn_id=request.turn_id,
            )
            yield RuntimeEvent(
                name=TurnEvent.TURN_WAITING_FOR_APPROVAL,
                runtime=runtime,
                correlation_id=request.correlation_id,
                turn_id=request.turn_id,
                payload={
                    "request": {
                        "request_id": "approval-1",
                        "permission": "write",
                    }
                },
            )

        def reply_approval(self, decision):
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.INTERACTION_UNSUPPORTED,
                    message="reply failed",
                )
            )

    capability = CapabilityRecord(
        capability=INTERACTION_APPROVAL_CAPABILITY,
        runtime=runtime,
        support=CapabilitySupport.SUPPORTED,
        evidence=EvidenceLevel.INTEGRATION_VERIFIED,
        evidence_source="test integration",
    )
    runner = RuntimeTurnRunner(FailingReplyAdapter(), runtime, (capability,))
    outcome = {}
    thread = threading.Thread(
        target=lambda: outcome.update(result=runner.run(request))
    )
    thread.start()
    for _ in range(100):
        active = runner.active_interaction
        if active is not None and active.state is InteractionState.WAITING_APPROVAL:
            break
        threading.Event().wait(0.01)

    with pytest.raises(RuntimeTurnAdapterError, match="reply failed"):
        runner.reply_approval(
            "approval-1",
            ApprovalOutcome.REJECTED,
            "user:andy",
        )
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert outcome["result"].state is TurnState.CANCELLED
    assert not any(
        event.name is InteractionEvent.APPROVAL_DECIDED
        for event in outcome["result"].events
    )


def test_runner_rejects_concurrent_run_without_replacing_active_turn():
    import threading

    runtime = RuntimeIdentity(
        runtime_id="local-fake",
        runtime_kind="fake",
        runtime_version="1.2.3",
        channel=ChannelMode.TRANSIENT_PROCESS,
    )
    started = threading.Event()
    release = threading.Event()

    class BlockingAdapter:
        def iter_turn_events(self, runtime, request, control):
            yield RuntimeEvent(
                name=TurnEvent.TURN_ACCEPTED,
                runtime=runtime,
                correlation_id=request.correlation_id,
                turn_id=request.turn_id,
            )
            started.set()
            release.wait(2)
            yield RuntimeEvent(
                name=TurnEvent.TURN_SUCCEEDED,
                runtime=runtime,
                correlation_id=request.correlation_id,
                turn_id=request.turn_id,
            )

        def reply_approval(self, decision):
            raise AssertionError("no approval expected")

    runner = RuntimeTurnRunner(BlockingAdapter(), runtime)
    first = RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt="hello",
        working_directory="/tmp/project",
    )
    outcome = {}
    thread = threading.Thread(
        target=lambda: outcome.update(result=runner.run(first))
    )
    thread.start()
    assert started.wait(1)

    second = first.model_copy(
        update={"turn_id": "turn-2", "correlation_id": "request-2"}
    )
    with pytest.raises(RuntimeError, match="active turn"):
        runner.run(second)

    assert runner.active_interaction is not None
    release.set()
    thread.join(timeout=2)
    assert outcome["result"].state is TurnState.SUCCEEDED
