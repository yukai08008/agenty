"""Pure TurnMachine driven by normalized Runtime events."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agenty.runtime.protocol import (
    OutputEvent,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeIdentity,
    RuntimeTurnRequest,
    TurnEvent,
    TurnState,
)


class InvalidTurnTransition(RuntimeError):
    pass


_TRANSITIONS = {
    (None, TurnEvent.TURN_CREATED): TurnState.CREATED,
    (TurnState.CREATED, TurnEvent.TURN_SUBMISSION_STARTED): TurnState.SUBMITTING,
    (TurnState.SUBMITTING, TurnEvent.TURN_ACCEPTED): TurnState.RUNNING,
    (TurnState.SUBMITTING, TurnEvent.TURN_FAILED): TurnState.FAILED,
    (TurnState.RUNNING, TurnEvent.TURN_WAITING_FOR_INPUT): (
        TurnState.WAITING_INPUT
    ),
    (TurnState.WAITING_INPUT, TurnEvent.TURN_INPUT_SUPPLIED): TurnState.RUNNING,
    (TurnState.RUNNING, TurnEvent.TURN_WAITING_FOR_APPROVAL): (
        TurnState.WAITING_APPROVAL
    ),
    (TurnState.WAITING_APPROVAL, TurnEvent.TURN_APPROVAL_RESOLVED): (
        TurnState.RUNNING
    ),
    (TurnState.RUNNING, TurnEvent.TURN_SUCCEEDED): TurnState.SUCCEEDED,
    (TurnState.RUNNING, TurnEvent.TURN_FAILED): TurnState.FAILED,
    (TurnState.WAITING_INPUT, TurnEvent.TURN_FAILED): TurnState.FAILED,
    (TurnState.WAITING_APPROVAL, TurnEvent.TURN_FAILED): TurnState.FAILED,
    (TurnState.RUNNING, TurnEvent.TURN_CANCELLED): TurnState.CANCELLED,
    (TurnState.RUNNING, TurnEvent.TURN_TIMED_OUT): TurnState.TIMED_OUT,
    (TurnState.WAITING_INPUT, TurnEvent.TURN_TIMED_OUT): TurnState.TIMED_OUT,
    (TurnState.WAITING_APPROVAL, TurnEvent.TURN_TIMED_OUT): TurnState.TIMED_OUT,
}

_OUTPUT_STATES = {
    TurnState.RUNNING,
    TurnState.WAITING_INPUT,
    TurnState.WAITING_APPROVAL,
}

_FAILURE_EVENTS = {TurnEvent.TURN_FAILED, TurnEvent.TURN_TIMED_OUT}


class TurnStateData(BaseModel):
    """Validated and serializable state owned by one TurnMachine."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    runtime: RuntimeIdentity
    request: RuntimeTurnRequest
    state: TurnState | None = None
    session_id: str | None = None
    failure: RuntimeFailure | None = None
    events: list[RuntimeEvent] = Field(default_factory=list)


class TurnMachine:
    def __init__(
        self,
        runtime: RuntimeIdentity,
        request: RuntimeTurnRequest,
        state_data: TurnStateData | None = None,
    ) -> None:
        if state_data is not None and (
            state_data.runtime != runtime or state_data.request != request
        ):
            raise ValueError("state data belongs to another runtime or turn")
        self._data = state_data or TurnStateData(runtime=runtime, request=request)

    @property
    def data(self) -> TurnStateData:
        return self._data

    @property
    def state(self) -> TurnState | None:
        return self._data.state

    @property
    def events(self) -> tuple[RuntimeEvent, ...]:
        return tuple(self._data.events)

    def apply(self, event: RuntimeEvent) -> TurnState:
        self._validate_context(event)

        if isinstance(event.name, OutputEvent):
            if self.state not in _OUTPUT_STATES:
                raise InvalidTurnTransition(
                    f"cannot apply output from {self._state_name()}"
                )
            self._accept_session(event)
            self._data.events.append(event)
            assert self.state is not None
            return self.state

        if not isinstance(event.name, TurnEvent):
            raise InvalidTurnTransition(
                f"event {event.name.value!r} does not belong to TurnMachine"
            )

        next_state = _TRANSITIONS.get((self.state, event.name))
        if next_state is None:
            raise InvalidTurnTransition(
                f"cannot apply {event.name.value!r} from {self._state_name()}"
            )

        failure = self._failure_from(event)
        self._accept_session(event)
        self._data.failure = failure
        self._data.state = next_state
        self._data.events.append(event)
        return next_state

    def snapshot(self) -> TurnStateData:
        return self._data.model_copy(deep=True)

    def _validate_context(self, event: RuntimeEvent) -> None:
        if event.runtime != self._data.runtime:
            raise InvalidTurnTransition("event belongs to another runtime")
        if event.turn_id != self._data.request.turn_id:
            raise InvalidTurnTransition("event belongs to another turn")
        if event.correlation_id != self._data.request.correlation_id:
            raise InvalidTurnTransition("event has another correlation id")
        if (
            self._data.session_id is not None
            and event.session_id is not None
            and event.session_id != self._data.session_id
        ):
            raise InvalidTurnTransition("event belongs to another session")

    def _failure_from(self, event: RuntimeEvent) -> RuntimeFailure | None:
        if event.name not in _FAILURE_EVENTS:
            return None
        failure = event.payload.get("failure")
        if not isinstance(failure, RuntimeFailure):
            raise InvalidTurnTransition(
                "failure event requires a RuntimeFailure payload"
            )
        return failure

    def _accept_session(self, event: RuntimeEvent) -> None:
        if self._data.session_id is None and event.session_id is not None:
            self._data.session_id = event.session_id

    def _state_name(self) -> str:
        return "none" if self.state is None else repr(self.state.value)
