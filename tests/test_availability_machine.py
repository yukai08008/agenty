import pytest

from agenty.runtime.availability import (
    AvailabilityMachine,
    AvailabilityStateData,
    InvalidAvailabilityTransition,
)
from agenty.runtime.protocol import (
    AvailabilityEvent,
    AvailabilityState,
    CapabilityRecord,
    CapabilitySupport,
    ChannelMode,
    EvidenceLevel,
    RuntimeEvent,
    RuntimeIdentity,
    TurnEvent,
)


def runtime(version: str | None = None) -> RuntimeIdentity:
    return RuntimeIdentity(
        runtime_id="local-runtime",
        runtime_kind="fake",
        runtime_version=version,
        channel=ChannelMode.TRANSIENT_PROCESS,
    )


def event(
    name: AvailabilityEvent,
    identity: RuntimeIdentity,
    payload: dict[str, object] | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        name=name,
        runtime=identity,
        correlation_id="probe-1",
        payload=payload or {},
    )


def test_successful_probe_reaches_available_with_capabilities():
    machine = AvailabilityMachine(runtime())
    detected = runtime("1.2.3")
    capability = CapabilityRecord(
        capability="session.fork",
        runtime=detected,
        support=CapabilitySupport.SUPPORTED,
        evidence=EvidenceLevel.SOURCE_CONFIRMED,
        evidence_source="runtime source v1.2.3",
    )

    machine.apply(event(AvailabilityEvent.PROBE_STARTED, runtime()))
    machine.apply(event(AvailabilityEvent.RUNTIME_DETECTED, detected))
    machine.apply(
        event(
            AvailabilityEvent.CAPABILITIES_RESOLVED,
            detected,
            {"capabilities": (capability,)},
        )
    )

    snapshot = machine.snapshot()
    assert snapshot.availability is AvailabilityState.AVAILABLE
    assert snapshot.runtime.runtime_version == "1.2.3"
    assert snapshot.capabilities == (capability,)
    assert snapshot.sequence == 3


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (AvailabilityEvent.RUNTIME_MISSING, AvailabilityState.UNAVAILABLE),
        (
            AvailabilityEvent.RUNTIME_INCOMPATIBLE,
            AvailabilityState.INCOMPATIBLE,
        ),
    ],
)
def test_missing_and_incompatible_are_distinct(result, expected):
    identity = runtime()
    machine = AvailabilityMachine(identity)

    machine.apply(event(AvailabilityEvent.PROBE_STARTED, identity))
    machine.apply(event(result, identity))

    assert machine.state is expected


def test_partial_capability_probe_is_degraded():
    machine = AvailabilityMachine(runtime())
    detected = runtime("1.2.3")

    machine.apply(event(AvailabilityEvent.PROBE_STARTED, runtime()))
    machine.apply(event(AvailabilityEvent.RUNTIME_DETECTED, detected))
    machine.apply(
        event(AvailabilityEvent.CAPABILITY_PROBE_FAILED, detected)
    )

    assert machine.state is AvailabilityState.DEGRADED


def test_capability_result_requires_runtime_detection():
    identity = runtime()
    machine = AvailabilityMachine(identity)
    machine.apply(event(AvailabilityEvent.PROBE_STARTED, identity))

    with pytest.raises(InvalidAvailabilityTransition):
        machine.apply(
            event(AvailabilityEvent.CAPABILITIES_RESOLVED, identity)
        )

    assert machine.state is AvailabilityState.PROBING
    assert len(machine.events) == 1


def test_wrong_domain_or_runtime_is_rejected_without_mutation():
    machine = AvailabilityMachine(runtime())
    wrong_domain = RuntimeEvent(
        name=TurnEvent.TURN_CREATED,
        runtime=runtime(),
        correlation_id="turn-1",
    )

    with pytest.raises(InvalidAvailabilityTransition):
        machine.apply(wrong_domain)
    with pytest.raises(InvalidAvailabilityTransition):
        machine.apply(
            event(
                AvailabilityEvent.PROBE_STARTED,
                RuntimeIdentity(runtime_id="other", runtime_kind="fake"),
            )
        )

    assert machine.state is AvailabilityState.UNKNOWN
    assert machine.events == ()


def test_conditional_capability_requires_constraints():
    with pytest.raises(ValueError, match="requires constraints"):
        CapabilityRecord(
            capability="approval.interactive",
            runtime=runtime("1.2.3"),
            support=CapabilitySupport.CONDITIONAL,
            evidence=EvidenceLevel.SOURCE_CONFIRMED,
            evidence_source="runtime source v1.2.3",
        )


@pytest.mark.parametrize(
    "identity",
    [
        RuntimeIdentity(
            runtime_id="runtime",
            runtime_kind="fake",
            channel=ChannelMode.TRANSIENT_PROCESS,
        ),
        RuntimeIdentity(
            runtime_id="runtime",
            runtime_kind="fake",
            runtime_version="1.2.3",
        ),
    ],
)
def test_capability_requires_version_and_channel(identity):
    with pytest.raises(ValueError, match="requires"):
        CapabilityRecord(
            capability="session.fork",
            runtime=identity,
            support=CapabilitySupport.SUPPORTED,
            evidence=EvidenceLevel.SOURCE_CONFIRMED,
            evidence_source="runtime source",
        )


def test_support_claim_requires_evidence():
    with pytest.raises(ValueError, match="requires evidence"):
        CapabilityRecord(
            capability="session.fork",
            runtime=runtime("1.2.3"),
            support=CapabilitySupport.SUPPORTED,
            evidence=EvidenceLevel.UNKNOWN,
        )


def test_capability_key_is_scoped_by_runtime_version_and_channel():
    identity = runtime("1.2.3")
    record = CapabilityRecord(
        capability="session.fork",
        runtime=identity,
        support=CapabilitySupport.SUPPORTED,
        evidence=EvidenceLevel.PROBE_VERIFIED,
        evidence_source="contract probe",
    )

    assert record.key == (
        "fake",
        "1.2.3",
        ChannelMode.TRANSIENT_PROCESS,
        "session.fork",
    )


def test_availability_state_data_round_trips_and_restores_machine():
    identity = runtime("1.2.3")
    machine = AvailabilityMachine(identity)
    machine.apply(event(AvailabilityEvent.PROBE_STARTED, identity))
    machine.apply(event(AvailabilityEvent.RUNTIME_DETECTED, identity))
    machine.apply(
        event(AvailabilityEvent.CAPABILITIES_RESOLVED, identity)
    )

    restored_data = AvailabilityStateData.model_validate_json(
        machine.data.model_dump_json()
    )
    restored_machine = AvailabilityMachine(restored_data.runtime, restored_data)

    assert restored_machine.state is AvailabilityState.AVAILABLE
    assert restored_machine.snapshot().sequence == 3
