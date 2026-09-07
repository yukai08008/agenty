import pytest

from agenty.runtime.events import (
    InvalidRuntimeEventStream,
    RuntimeEventStreamMachine,
    RuntimeEventStreamState,
    RuntimeEventStreamStateData,
)
from agenty.runtime.protocol import (
    ChannelMode,
    OutputEvent,
    RuntimeEvent,
    RuntimeIdentity,
    TurnEvent,
)


def runtime(runtime_id: str = "local-runtime") -> RuntimeIdentity:
    return RuntimeIdentity(
        runtime_id=runtime_id,
        runtime_kind="fake",
        runtime_version="1.2.3",
        channel=ChannelMode.TRANSIENT_PROCESS,
    )


def event(
    name=OutputEvent.TEXT_EMITTED,
    *,
    identity: RuntimeIdentity | None = None,
    correlation_id: str = "request-1",
    turn_id: str = "turn-1",
    session_id: str | None = None,
    sequence: int | None = None,
    raw_event=None,
) -> RuntimeEvent:
    return RuntimeEvent(
        name=name,
        runtime=identity or runtime(),
        correlation_id=correlation_id,
        turn_id=turn_id,
        session_id=session_id,
        sequence=sequence,
        payload={"text": "hello"},
        raw_event=raw_event,
    )


def stream() -> RuntimeEventStreamMachine:
    machine = RuntimeEventStreamMachine(
        runtime(),
        "request-1",
        turn_id="turn-1",
    )
    machine.start()
    return machine


def test_event_stream_assigns_contiguous_sequence_and_isolates_raw_data():
    machine = stream()

    first = machine.append(event(TurnEvent.TURN_CREATED))
    second = machine.append(
        event(
            session_id="session-1",
            raw_event={"type": "text", "vendorField": True},
        )
    )

    assert [first.sequence, second.sequence] == [1, 2]
    assert first.raw_event is None
    assert second.raw_event is None
    assert second.payload == {"text": "hello"}
    assert machine.data.session_id == "session-1"
    assert machine.data.raw_events[0].sequence == 2
    assert machine.data.raw_events[0].data["vendorField"] is True


def test_event_stream_rejects_non_json_raw_evidence_without_mutation():
    machine = stream()
    before = machine.snapshot()

    with pytest.raises(InvalidRuntimeEventStream, match="JSON-compatible"):
        machine.append(event(raw_event={"invalid": object()}))

    assert machine.snapshot() == before


def test_event_stream_rejects_non_finite_raw_evidence_without_mutation():
    machine = stream()
    before = machine.snapshot()

    with pytest.raises(InvalidRuntimeEventStream, match="JSON-compatible"):
        machine.append(event(raw_event={"invalid": float("nan")}))

    assert machine.snapshot() == before


@pytest.mark.parametrize(
    "bad_event",
    [
        event(identity=runtime("other")),
        event(correlation_id="other"),
        event(turn_id="other"),
    ],
)
def test_event_stream_rejects_context_drift_without_mutation(bad_event):
    machine = stream()
    before = machine.snapshot()

    with pytest.raises(InvalidRuntimeEventStream):
        machine.append(bad_event)

    assert machine.snapshot() == before


def test_event_stream_locks_first_session_id():
    machine = stream()
    machine.append(event(session_id="session-1"))
    before = machine.snapshot()

    with pytest.raises(InvalidRuntimeEventStream, match="another session"):
        machine.append(event(session_id="session-2"))

    assert machine.snapshot() == before


def test_adapter_cannot_assign_public_sequence():
    machine = stream()

    with pytest.raises(InvalidRuntimeEventStream, match="cannot assign"):
        machine.append(event(sequence=9))

    assert machine.data.events == ()


def test_closed_stream_rejects_more_events():
    machine = stream()
    machine.append(event())

    result = machine.close()

    assert result.state is RuntimeEventStreamState.CLOSED
    with pytest.raises(InvalidRuntimeEventStream, match="cannot append"):
        machine.append(event())


def test_event_stream_state_round_trips_and_restores():
    machine = stream()
    machine.append(event(session_id="session-1", raw_event={"type": "text"}))
    machine.close()

    restored_data = RuntimeEventStreamStateData.model_validate_json(
        machine.data.model_dump_json()
    )
    restored = RuntimeEventStreamMachine(
        runtime(),
        "request-1",
        turn_id="turn-1",
        state_data=restored_data,
    )

    assert restored.snapshot() == machine.snapshot()


def test_state_data_rejects_noncontiguous_sequence():
    with pytest.raises(ValueError, match="contiguous"):
        RuntimeEventStreamStateData(
            runtime=runtime(),
            correlation_id="request-1",
            turn_id="turn-1",
            state=RuntimeEventStreamState.ACTIVE,
            events=(event(sequence=2),),
        )


def test_idle_state_data_cannot_contain_events():
    with pytest.raises(ValueError, match="idle event stream"):
        RuntimeEventStreamStateData(
            runtime=runtime(),
            correlation_id="request-1",
            turn_id="turn-1",
            events=(event(sequence=1),),
        )
