import pytest

from agenty.runtime.interaction import (
    InteractionState,
    InteractionStateData,
    InvalidInteraction,
    RuntimeInteractionMachine,
)
from agenty.runtime.protocol import (
    INTERACTION_APPROVAL_CAPABILITY,
    INTERACTION_AUTO_APPROVE_CAPABILITY,
    ApprovalOutcome,
    CapabilityRecord,
    CapabilitySupport,
    ChannelMode,
    EvidenceLevel,
    InteractionEvent,
    InteractionPolicyMode,
    RuntimeApprovalRequest,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeInteractionPolicy,
)


def runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        runtime_id="local-runtime",
        runtime_kind="fake",
        runtime_version="1.2.3",
        channel=ChannelMode.MANAGED_SERVER,
    )


def capability(name: str) -> CapabilityRecord:
    return CapabilityRecord(
        capability=name,
        runtime=runtime(),
        support=CapabilitySupport.SUPPORTED,
        evidence=EvidenceLevel.INTEGRATION_VERIFIED,
        evidence_source="test integration",
    )


def machine(mode: InteractionPolicyMode) -> RuntimeInteractionMachine:
    return RuntimeInteractionMachine(
        runtime(),
        "turn-1",
        "request-1",
        RuntimeInteractionPolicy(mode=mode),
    )


def approval() -> RuntimeApprovalRequest:
    return RuntimeApprovalRequest(
        request_id="approval-1",
        permission="write",
        description="write a project file",
    )


def test_default_policy_rejects_automatically_and_round_trips():
    interaction = RuntimeInteractionPolicy()
    assert interaction.mode is InteractionPolicyMode.DENY_BY_DEFAULT

    policy_machine = RuntimeInteractionMachine(
        runtime(), "turn-1", "request-1", interaction
    )
    policy_machine.prepare(())

    assert [event.name for event in policy_machine.data.audit_events] == [
        InteractionEvent.INTERACTION_POLICY_APPLIED,
    ]
    restored_data = InteractionStateData.model_validate_json(
        policy_machine.data.model_dump_json()
    )
    assert restored_data == policy_machine.data


def test_ask_requires_supported_round_trip_capability():
    policy_machine = machine(InteractionPolicyMode.ASK)

    with pytest.raises(InvalidInteraction) as caught:
        policy_machine.prepare(())

    assert caught.value.failure is not None
    assert (
        caught.value.failure.code
        is RuntimeFailureCode.INTERACTION_UNSUPPORTED
    )
    assert policy_machine.data.audit_events == []


def test_ask_waits_for_matching_human_decision_and_audits_actor():
    policy_machine = machine(InteractionPolicyMode.ASK)
    policy_machine.prepare((capability(INTERACTION_APPROVAL_CAPABILITY),))

    request_event = policy_machine.request_approval(approval())

    assert request_event.name is InteractionEvent.APPROVAL_REQUESTED
    assert policy_machine.state is InteractionState.WAITING_APPROVAL

    with pytest.raises(InvalidInteraction, match="does not match"):
        policy_machine.propose_decision(
            "other",
            outcome=ApprovalOutcome.APPROVED,
            actor="user:andy",
        )

    decision = policy_machine.propose_decision(
        "approval-1",
        outcome=ApprovalOutcome.APPROVED,
        actor="user:andy",
    )
    event = policy_machine.commit_decision(decision)
    assert event.name is InteractionEvent.APPROVAL_DECIDED
    assert decision.outcome is ApprovalOutcome.APPROVED
    assert decision.actor == "user:andy"
    assert decision.automatic is False
    assert policy_machine.state is InteractionState.READY


@pytest.mark.parametrize(
    ("mode", "outcome"),
    [
        (InteractionPolicyMode.AUTO_APPROVE, ApprovalOutcome.APPROVED),
        (InteractionPolicyMode.AUTO_REJECT, ApprovalOutcome.REJECTED),
        (InteractionPolicyMode.DENY_BY_DEFAULT, ApprovalOutcome.REJECTED),
    ],
)
def test_automatic_policies_resolve_permission_requests(mode, outcome):
    policy_machine = machine(mode)
    capabilities = (
        (capability(INTERACTION_AUTO_APPROVE_CAPABILITY),)
        if mode is InteractionPolicyMode.AUTO_APPROVE
        else ()
    )
    policy_machine.prepare(capabilities)

    policy_machine.request_approval(approval())
    decision = policy_machine.propose_decision("approval-1")
    policy_machine.commit_decision(decision)

    assert decision is not None
    assert decision.outcome is outcome
    assert decision.actor == f"policy:{mode.value}"
    assert decision.automatic is True
    assert policy_machine.state is InteractionState.READY


def test_cancel_request_is_audited():
    policy_machine = machine(InteractionPolicyMode.DENY_BY_DEFAULT)
    policy_machine.prepare(())

    event = policy_machine.cancel_requested("user:andy")

    assert event.name is InteractionEvent.TURN_CANCEL_REQUESTED
    assert event.payload == {"actor": "user:andy"}


def test_advertised_only_capability_cannot_enable_auto_approve():
    policy_machine = machine(InteractionPolicyMode.AUTO_APPROVE)
    advertised = capability(INTERACTION_AUTO_APPROVE_CAPABILITY).model_copy(
        update={"evidence": EvidenceLevel.ADVERTISED}
    )

    with pytest.raises(InvalidInteraction) as caught:
        policy_machine.prepare((advertised,))

    assert caught.value.failure is not None
    assert caught.value.failure.code is RuntimeFailureCode.INTERACTION_UNSUPPORTED


@pytest.mark.parametrize(
    ("state", "pending"),
    [
        (InteractionState.WAITING_APPROVAL, None),
        (InteractionState.READY, approval()),
    ],
)
def test_restored_state_rejects_pending_request_mismatch(state, pending):
    with pytest.raises(ValueError, match="pending request"):
        InteractionStateData(
            runtime=runtime(),
            turn_id="turn-1",
            correlation_id="request-1",
            policy=RuntimeInteractionPolicy(),
            state=state,
            pending_request=pending,
        )
