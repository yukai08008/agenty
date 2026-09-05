import pytest
from pydantic import ValidationError

from agenty.runtime.protocol import (
    ChannelMode,
    OutputEvent,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeTurnRequest,
    TurnEvent,
    TurnState,
)
from agenty.runtime.turn import (
    InvalidTurnTransition,
    TurnMachine,
    TurnStateData,
)


def runtime(runtime_id: str = "local-runtime") -> RuntimeIdentity:
    return RuntimeIdentity(
        runtime_id=runtime_id,
        runtime_kind="fake",
        runtime_version="1.2.3",
        channel=ChannelMode.TRANSIENT_PROCESS,
    )


def request(**updates) -> RuntimeTurnRequest:
    values = {
        "turn_id": "turn-1",
        "correlation_id": "request-1",
        "prompt": "Answer with one word",
        "working_directory": "/tmp/project",
    }
    values.update(updates)
    return RuntimeTurnRequest(**values)


def event(
    name,
    *,
    identity: RuntimeIdentity | None = None,
    turn_id: str = "turn-1",
    correlation_id: str = "request-1",
    session_id: str | None = None,
    payload: dict | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        name=name,
        runtime=identity or runtime(),
        turn_id=turn_id,
        correlation_id=correlation_id,
        session_id=session_id,
        payload=payload or {},
    )


def start_running(machine: TurnMachine) -> None:
    machine.apply(event(TurnEvent.TURN_CREATED))
    machine.apply(event(TurnEvent.TURN_SUBMISSION_STARTED))
    machine.apply(event(TurnEvent.TURN_ACCEPTED, session_id="session-1"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("turn_id", ""),
        ("correlation_id", " "),
        ("prompt", ""),
        ("working_directory", " "),
    ],
)
def test_turn_request_rejects_empty_required_text(field, value):
    with pytest.raises(ValidationError, match="must not be empty"):
        request(**{field: value})


def test_turn_happy_path_records_session_and_succeeds():
    machine = TurnMachine(runtime(), request())

    start_running(machine)
    machine.apply(event(OutputEvent.TEXT_EMITTED, session_id="session-1"))
    machine.apply(event(TurnEvent.TURN_SUCCEEDED, session_id="session-1"))

    assert machine.state is TurnState.SUCCEEDED
    assert machine.data.session_id == "session-1"
    assert len(machine.events) == 5


def test_output_is_accepted_while_running_without_changing_state():
    machine = TurnMachine(runtime(), request())
    start_running(machine)

    state = machine.apply(
        event(OutputEvent.REASONING_EMITTED, session_id="session-1")
    )

    assert state is TurnState.RUNNING


def test_output_before_acceptance_is_rejected_without_mutation():
    machine = TurnMachine(runtime(), request())
    machine.apply(event(TurnEvent.TURN_CREATED))
    before = machine.snapshot()

    with pytest.raises(InvalidTurnTransition, match="cannot apply output"):
        machine.apply(event(OutputEvent.TEXT_EMITTED))

    assert machine.snapshot() == before


def test_illegal_lifecycle_event_is_rejected_without_mutation():
    machine = TurnMachine(runtime(), request())
    machine.apply(event(TurnEvent.TURN_CREATED))
    before = machine.snapshot()

    with pytest.raises(InvalidTurnTransition, match="cannot apply"):
        machine.apply(event(TurnEvent.TURN_SUCCEEDED))

    assert machine.snapshot() == before


def test_event_from_another_domain_is_rejected_without_mutation():
    from agenty.runtime.protocol import AvailabilityEvent

    machine = TurnMachine(runtime(), request())

    with pytest.raises(InvalidTurnTransition, match="does not belong"):
        machine.apply(event(AvailabilityEvent.PROBE_STARTED))

    assert machine.state is None
    assert machine.events == ()


@pytest.mark.parametrize(
    "bad_event",
    [
        event(TurnEvent.TURN_CREATED, identity=runtime("other")),
        event(TurnEvent.TURN_CREATED, turn_id="other"),
        event(TurnEvent.TURN_CREATED, correlation_id="other"),
    ],
)
def test_wrong_context_is_rejected_without_mutation(bad_event):
    machine = TurnMachine(runtime(), request())

    with pytest.raises(InvalidTurnTransition):
        machine.apply(bad_event)

    assert machine.state is None
    assert machine.events == ()


def test_session_cannot_change_during_turn():
    machine = TurnMachine(runtime(), request())
    start_running(machine)
    before = machine.snapshot()

    with pytest.raises(InvalidTurnTransition, match="another session"):
        machine.apply(event(OutputEvent.TEXT_EMITTED, session_id="session-2"))

    assert machine.snapshot() == before


@pytest.mark.parametrize(
    ("terminal_event", "terminal_state", "code"),
    [
        (
            TurnEvent.TURN_FAILED,
            TurnState.FAILED,
            RuntimeFailureCode.TURN_FAILED,
        ),
        (
            TurnEvent.TURN_TIMED_OUT,
            TurnState.TIMED_OUT,
            RuntimeFailureCode.TURN_TIMEOUT,
        ),
    ],
)
def test_failure_terminal_states_require_and_store_failure(
    terminal_event,
    terminal_state,
    code,
):
    machine = TurnMachine(runtime(), request())
    start_running(machine)
    failure = RuntimeFailure(code=code, message="turn did not complete")

    machine.apply(
        event(
            terminal_event,
            session_id="session-1",
            payload={"failure": failure},
        )
    )

    assert machine.state is terminal_state
    assert machine.data.failure == failure


def test_failure_without_structured_reason_is_rejected():
    machine = TurnMachine(runtime(), request())
    start_running(machine)
    before = machine.snapshot()

    with pytest.raises(InvalidTurnTransition, match="RuntimeFailure"):
        machine.apply(event(TurnEvent.TURN_FAILED, session_id="session-1"))

    assert machine.snapshot() == before


def test_turn_state_data_round_trips_and_restores_machine():
    machine = TurnMachine(runtime(), request())
    start_running(machine)

    restored_data = TurnStateData.model_validate_json(
        machine.data.model_dump_json()
    )
    restored = TurnMachine(runtime(), request(), restored_data)
    restored.apply(event(TurnEvent.TURN_SUCCEEDED, session_id="session-1"))

    assert restored.state is TurnState.SUCCEEDED
    assert restored.data.session_id == "session-1"
