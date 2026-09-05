import pytest
from pydantic import BaseModel, ValidationError

from agenty.runtime.protocol import (
    AvailabilityEvent,
    AvailabilityState,
    ChannelEvent,
    ChannelMode,
    ChannelState,
    OutputEvent,
    RuntimeEvent,
    RuntimeIdentity,
    RuntimeSnapshot,
    SessionEvent,
    SessionState,
    TurnEvent,
    TurnState,
)


def test_runtime_snapshot_keeps_child_machine_states_independent():
    runtime = RuntimeIdentity(
        runtime_id="local-opencode",
        runtime_kind="opencode",
        runtime_version="1.18.26",
        channel=ChannelMode.TRANSIENT_PROCESS,
    )

    snapshot = RuntimeSnapshot(
        runtime=runtime,
        availability=AvailabilityState.AVAILABLE,
        channel=ChannelState.DETACHED,
        session=SessionState.READY,
        turn=None,
        session_id="session-1",
    )

    assert snapshot.availability is AvailabilityState.AVAILABLE
    assert snapshot.channel is ChannelState.DETACHED
    assert snapshot.session is SessionState.READY
    assert snapshot.turn is None


def test_normalized_event_carries_runtime_and_correlation_context():
    runtime = RuntimeIdentity(
        runtime_id="local-opencode",
        runtime_kind="opencode",
        runtime_version="1.18.26",
    )

    event = RuntimeEvent(
        name=TurnEvent.TURN_ACCEPTED,
        runtime=runtime,
        correlation_id="request-1",
        session_id="session-1",
        turn_id="turn-1",
        payload={"accepted": True},
    )

    assert event.runtime == runtime
    assert event.correlation_id == "request-1"
    assert event.session_id == "session-1"
    assert event.turn_id == "turn-1"


def test_public_event_names_are_unique_across_domains():
    event_types = (
        AvailabilityEvent,
        ChannelEvent,
        SessionEvent,
        TurnEvent,
        OutputEvent,
    )
    names = [event.value for event_type in event_types for event in event_type]

    assert len(names) == len(set(names))


def test_public_protocol_has_no_vendor_specific_fields():
    public_models = (RuntimeIdentity, RuntimeEvent, RuntimeSnapshot)
    field_names = {
        field_name.lower()
        for model in public_models
        for field_name in model.model_fields
    }

    assert not field_names & {"opencode", "codex", "claude", "variant"}


def test_public_protocol_models_use_pydantic_and_round_trip_json():
    public_models = (RuntimeIdentity, RuntimeEvent, RuntimeSnapshot)
    assert all(issubclass(model, BaseModel) for model in public_models)

    snapshot = RuntimeSnapshot(
        runtime=RuntimeIdentity(
            runtime_id="local-runtime",
            runtime_kind="fake",
            runtime_version="1.2.3",
            channel=ChannelMode.TRANSIENT_PROCESS,
        ),
        availability=AvailabilityState.AVAILABLE,
    )

    restored = RuntimeSnapshot.model_validate_json(snapshot.model_dump_json())
    assert restored == snapshot


def test_public_protocol_rejects_unknown_fields():
    with pytest.raises(ValidationError, match="vendor_option"):
        RuntimeIdentity.model_validate(
            {
                "runtime_id": "local-runtime",
                "runtime_kind": "fake",
                "vendor_option": True,
            }
        )


def test_current_baseline_does_not_add_unconfirmed_transition_states():
    assert "cancelling" not in {state.value for state in TurnState}
    assert "deleting" not in {state.value for state in SessionState}


def test_package_root_exports_the_new_protocol_snapshot_and_event():
    from agenty.runtime import RuntimeEvent as ExportedRuntimeEvent
    from agenty.runtime import RuntimeSnapshot as ExportedRuntimeSnapshot

    assert ExportedRuntimeEvent is RuntimeEvent
    assert ExportedRuntimeSnapshot is RuntimeSnapshot
