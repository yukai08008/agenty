"""Ordered public event stream with raw diagnostic isolation."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agenty.runtime.protocol import RuntimeEvent, RuntimeIdentity


class RuntimeEventStreamState(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    CLOSED = "closed"


class RuntimeRawEventRecord(BaseModel):
    """Diagnostic copy that is deliberately separate from public events."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int = Field(ge=1)
    data: Any


class RuntimeEventStreamStateData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: RuntimeIdentity
    correlation_id: str
    turn_id: str | None = None
    session_id: str | None = None
    state: RuntimeEventStreamState = RuntimeEventStreamState.IDLE
    events: tuple[RuntimeEvent, ...] = ()
    raw_events: tuple[RuntimeRawEventRecord, ...] = ()

    @field_validator("correlation_id")
    @classmethod
    def validate_correlation_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("correlation_id must not be empty")
        return value

    @model_validator(mode="after")
    def validate_sequence(self) -> "RuntimeEventStreamStateData":
        if self.state is RuntimeEventStreamState.IDLE and (
            self.session_id is not None or self.events or self.raw_events
        ):
            raise ValueError("idle event stream cannot retain event context")
        expected = list(range(1, len(self.events) + 1))
        actual = [event.sequence for event in self.events]
        if actual != expected:
            raise ValueError("public event sequence must be contiguous")
        event_sequences = set(expected)
        if any(raw.sequence not in event_sequences for raw in self.raw_events):
            raise ValueError("raw event must reference a public event sequence")
        raw_sequences = [raw.sequence for raw in self.raw_events]
        if raw_sequences != sorted(set(raw_sequences)):
            raise ValueError("raw event sequence must be unique and ordered")
        if any(event.raw_event is not None for event in self.events):
            raise ValueError("public events cannot retain raw event data")
        return self


class InvalidRuntimeEventStream(RuntimeError):
    pass


class RuntimeEventStreamMachine:
    def __init__(
        self,
        runtime: RuntimeIdentity,
        correlation_id: str,
        *,
        turn_id: str | None = None,
        state_data: RuntimeEventStreamStateData | None = None,
    ) -> None:
        if state_data is not None and (
            state_data.runtime != runtime
            or state_data.correlation_id != correlation_id
            or state_data.turn_id != turn_id
        ):
            raise ValueError("state data belongs to another event stream")
        self._data = state_data or RuntimeEventStreamStateData(
            runtime=runtime,
            correlation_id=correlation_id,
            turn_id=turn_id,
        )

    @property
    def data(self) -> RuntimeEventStreamStateData:
        return self._data

    @property
    def state(self) -> RuntimeEventStreamState:
        return self._data.state

    def start(self) -> RuntimeEventStreamStateData:
        if self.state is not RuntimeEventStreamState.IDLE:
            raise InvalidRuntimeEventStream(
                f"cannot start event stream from {self.state.value!r}"
            )
        self._replace(state=RuntimeEventStreamState.ACTIVE)
        return self.snapshot()

    def append(self, event: RuntimeEvent) -> RuntimeEvent:
        if self.state is not RuntimeEventStreamState.ACTIVE:
            raise InvalidRuntimeEventStream(
                f"cannot append event from {self.state.value!r}"
            )
        self._validate_context(event)
        if event.sequence is not None:
            raise InvalidRuntimeEventStream(
                "adapter event cannot assign public sequence"
            )

        sequence = len(self._data.events) + 1
        public_event = event.model_copy(
            update={"sequence": sequence, "raw_event": None}
        )
        raw_events = self._data.raw_events
        if event.raw_event is not None:
            raw_events = (
                *raw_events,
                RuntimeRawEventRecord(sequence=sequence, data=event.raw_event),
            )
        session_id = self._data.session_id or event.session_id
        self._replace(
            session_id=session_id,
            events=(*self._data.events, public_event),
            raw_events=raw_events,
        )
        return public_event

    def close(self) -> RuntimeEventStreamStateData:
        if self.state is not RuntimeEventStreamState.ACTIVE:
            raise InvalidRuntimeEventStream(
                f"cannot close event stream from {self.state.value!r}"
            )
        self._replace(state=RuntimeEventStreamState.CLOSED)
        return self.snapshot()

    def snapshot(self) -> RuntimeEventStreamStateData:
        return self._data.model_copy(deep=True)

    def _validate_context(self, event: RuntimeEvent) -> None:
        if event.runtime != self._data.runtime:
            raise InvalidRuntimeEventStream("event belongs to another runtime")
        if event.correlation_id != self._data.correlation_id:
            raise InvalidRuntimeEventStream("event has another correlation id")
        if event.turn_id != self._data.turn_id:
            raise InvalidRuntimeEventStream("event belongs to another turn")
        if (
            self._data.session_id is not None
            and event.session_id is not None
            and event.session_id != self._data.session_id
        ):
            raise InvalidRuntimeEventStream("event belongs to another session")

    def _replace(self, **updates: Any) -> None:
        values = {
            "runtime": self._data.runtime,
            "correlation_id": self._data.correlation_id,
            "turn_id": self._data.turn_id,
            "session_id": self._data.session_id,
            "state": self._data.state,
            "events": self._data.events,
            "raw_events": self._data.raw_events,
        }
        values.update(updates)
        self._data = RuntimeEventStreamStateData(**values)
