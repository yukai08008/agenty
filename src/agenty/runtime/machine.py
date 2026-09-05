"""Event-driven outer lifecycle for one runtime installation."""

from __future__ import annotations

from dataclasses import dataclass

from agenty.runtime.adapters import RuntimeAdapter, RuntimeAdapterError
from agenty.runtime.models import (
    RuntimeEvent,
    RuntimeEventType,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeInfo,
    RuntimeSnapshot,
    RuntimeState,
)


class InvalidRuntimeTransition(RuntimeError):
    pass


_TRANSITIONS = {
    (RuntimeState.UNKNOWN, RuntimeEventType.PROBE_REQUESTED): RuntimeState.PROBING,
    (RuntimeState.UNAVAILABLE, RuntimeEventType.PROBE_REQUESTED): RuntimeState.PROBING,
    (RuntimeState.DEGRADED, RuntimeEventType.PROBE_REQUESTED): RuntimeState.PROBING,
    (RuntimeState.READY, RuntimeEventType.PROBE_REQUESTED): RuntimeState.PROBING,
    (RuntimeState.PROBING, RuntimeEventType.PROBE_SUCCEEDED): RuntimeState.READY,
    (RuntimeState.PROBING, RuntimeEventType.PROBE_FAILED): RuntimeState.UNAVAILABLE,
    (RuntimeState.READY, RuntimeEventType.FAULT_DETECTED): RuntimeState.DEGRADED,
}


@dataclass
class RuntimeMachine:
    adapter: RuntimeAdapter

    def __post_init__(self) -> None:
        self.state = RuntimeState.UNKNOWN
        self.info: RuntimeInfo | None = None
        self.failure: RuntimeFailure | None = None
        self._events: list[RuntimeEvent] = []

    def send(self, event_type: RuntimeEventType) -> RuntimeState:
        if event_type == RuntimeEventType.CLOSE_REQUESTED:
            if self.state == RuntimeState.CLOSED:
                raise InvalidRuntimeTransition("runtime is already closed")
            next_state = RuntimeState.CLOSED
        else:
            next_state = _TRANSITIONS.get((self.state, event_type))
            if next_state is None:
                raise InvalidRuntimeTransition(
                    f"cannot send {event_type.value!r} from {self.state.value!r}"
                )

        previous = self.state
        self.state = next_state
        self._events.append(
            RuntimeEvent(type=event_type, from_state=previous, to_state=next_state)
        )
        return next_state

    def probe(self) -> RuntimeSnapshot:
        self.send(RuntimeEventType.PROBE_REQUESTED)
        self.info = None
        self.failure = None
        try:
            self.info = self.adapter.probe()
        except RuntimeAdapterError as exc:
            self.failure = exc.failure
            self.send(RuntimeEventType.PROBE_FAILED)
        except Exception as exc:  # protect the public state boundary
            self.failure = RuntimeFailure(
                code=RuntimeFailureCode.INTERNAL,
                message="runtime probe raised an unexpected error",
                details={"error_type": type(exc).__name__, "error": str(exc)},
            )
            self.send(RuntimeEventType.PROBE_FAILED)
        else:
            self.send(RuntimeEventType.PROBE_SUCCEEDED)
        return self.snapshot()

    def snapshot(self) -> RuntimeSnapshot:
        return RuntimeSnapshot(
            state=self.state,
            info=self.info,
            failure=self.failure,
            events=tuple(self._events),
        )
