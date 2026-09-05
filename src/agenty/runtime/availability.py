"""Pure AvailabilityMachine driven by normalized Runtime events."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agenty.runtime.protocol import (
    AvailabilityEvent,
    AvailabilityState,
    CapabilityRecord,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeIdentity,
    RuntimeSnapshot,
)


class InvalidAvailabilityTransition(RuntimeError):
    pass


_TRANSITIONS = {
    (AvailabilityState.UNKNOWN, AvailabilityEvent.PROBE_STARTED): (
        AvailabilityState.PROBING
    ),
    (AvailabilityState.UNAVAILABLE, AvailabilityEvent.PROBE_STARTED): (
        AvailabilityState.PROBING
    ),
    (AvailabilityState.INCOMPATIBLE, AvailabilityEvent.PROBE_STARTED): (
        AvailabilityState.PROBING
    ),
    (AvailabilityState.DEGRADED, AvailabilityEvent.PROBE_STARTED): (
        AvailabilityState.PROBING
    ),
    (AvailabilityState.AVAILABLE, AvailabilityEvent.PROBE_STARTED): (
        AvailabilityState.PROBING
    ),
    (AvailabilityState.PROBING, AvailabilityEvent.RUNTIME_DETECTED): (
        AvailabilityState.PROBING
    ),
    (AvailabilityState.PROBING, AvailabilityEvent.CAPABILITIES_RESOLVED): (
        AvailabilityState.AVAILABLE
    ),
    (AvailabilityState.PROBING, AvailabilityEvent.CAPABILITY_PROBE_FAILED): (
        AvailabilityState.DEGRADED
    ),
    (AvailabilityState.PROBING, AvailabilityEvent.RUNTIME_MISSING): (
        AvailabilityState.UNAVAILABLE
    ),
    (AvailabilityState.PROBING, AvailabilityEvent.RUNTIME_UNAVAILABLE): (
        AvailabilityState.UNAVAILABLE
    ),
    (AvailabilityState.PROBING, AvailabilityEvent.RUNTIME_INCOMPATIBLE): (
        AvailabilityState.INCOMPATIBLE
    ),
    (AvailabilityState.AVAILABLE, AvailabilityEvent.RUNTIME_DEGRADED): (
        AvailabilityState.DEGRADED
    ),
    (AvailabilityState.DEGRADED, AvailabilityEvent.RUNTIME_RECOVERED): (
        AvailabilityState.AVAILABLE
    ),
    (AvailabilityState.AVAILABLE, AvailabilityEvent.RUNTIME_LOST): (
        AvailabilityState.UNAVAILABLE
    ),
    (AvailabilityState.DEGRADED, AvailabilityEvent.RUNTIME_LOST): (
        AvailabilityState.UNAVAILABLE
    ),
}


class AvailabilityStateData(BaseModel):
    """Validated and serializable state owned by AvailabilityMachine."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    runtime: RuntimeIdentity
    state: AvailabilityState = AvailabilityState.UNKNOWN
    capabilities: tuple[CapabilityRecord, ...] = Field(default_factory=tuple)
    failure: RuntimeFailure | None = None
    events: list[RuntimeEvent] = Field(default_factory=list)
    runtime_detected: bool = False


class AvailabilityMachine:
    def __init__(
        self,
        runtime: RuntimeIdentity,
        state_data: AvailabilityStateData | None = None,
    ) -> None:
        if state_data is not None and (
            state_data.runtime.runtime_id != runtime.runtime_id
            or state_data.runtime.runtime_kind != runtime.runtime_kind
        ):
            raise ValueError("state data belongs to another runtime")
        self._data = state_data or AvailabilityStateData(runtime=runtime)

    @property
    def data(self) -> AvailabilityStateData:
        return self._data

    @property
    def runtime(self) -> RuntimeIdentity:
        return self._data.runtime

    @property
    def state(self) -> AvailabilityState:
        return self._data.state

    @property
    def capabilities(self) -> tuple[CapabilityRecord, ...]:
        return self._data.capabilities

    @property
    def failure(self) -> RuntimeFailure | None:
        return self._data.failure

    @property
    def events(self) -> tuple[RuntimeEvent, ...]:
        return tuple(self._data.events)

    def apply(self, event: RuntimeEvent) -> AvailabilityState:
        if not isinstance(event.name, AvailabilityEvent):
            raise InvalidAvailabilityTransition(
                f"event {event.name.value!r} does not belong to AvailabilityMachine"
            )
        self._validate_runtime(event.runtime)

        if event.name is AvailabilityEvent.RUNTIME_CLOSED:
            if self.state is AvailabilityState.CLOSED:
                raise InvalidAvailabilityTransition("runtime is already closed")
            next_state = AvailabilityState.CLOSED
        else:
            next_state = _TRANSITIONS.get((self.state, event.name))
            if next_state is None:
                raise InvalidAvailabilityTransition(
                    f"cannot apply {event.name.value!r} from {self.state.value!r}"
                )

        self._validate_event_context(event)
        self._apply_event_data(event)
        self._data.state = next_state
        self._data.events.append(event)
        return self.state

    def snapshot(self) -> RuntimeSnapshot:
        return RuntimeSnapshot(
            runtime=self.runtime,
            availability=self.state,
            capabilities=self.capabilities,
            failure=self.failure,
            sequence=len(self._data.events),
        )

    def _validate_runtime(self, runtime: RuntimeIdentity) -> None:
        if (
            runtime.runtime_id != self.runtime.runtime_id
            or runtime.runtime_kind != self.runtime.runtime_kind
        ):
            raise InvalidAvailabilityTransition("event belongs to another runtime")
        if (
            self.runtime.channel is not None
            and runtime.channel is not None
            and runtime.channel is not self.runtime.channel
        ):
            raise InvalidAvailabilityTransition("event belongs to another channel")

    def _validate_event_context(self, event: RuntimeEvent) -> None:
        if event.name in {
            AvailabilityEvent.CAPABILITIES_RESOLVED,
            AvailabilityEvent.CAPABILITY_PROBE_FAILED,
        } and not self._data.runtime_detected:
            raise InvalidAvailabilityTransition(
                "capability result requires runtime_detected first"
            )

    def _apply_event_data(self, event: RuntimeEvent) -> None:
        if event.name is AvailabilityEvent.PROBE_STARTED:
            self._data.capabilities = ()
            self._data.failure = None
            self._data.runtime_detected = False
            return

        if event.name is AvailabilityEvent.RUNTIME_DETECTED:
            self._data.runtime = event.runtime
            self._data.runtime_detected = True
            return

        if event.name in {
            AvailabilityEvent.CAPABILITIES_RESOLVED,
            AvailabilityEvent.CAPABILITY_PROBE_FAILED,
        }:
            records = event.payload.get("capabilities", ())
            if not isinstance(records, (tuple, list)) or not all(
                isinstance(record, CapabilityRecord) for record in records
            ):
                raise InvalidAvailabilityTransition(
                    "capabilities payload must contain CapabilityRecord values"
                )
            for record in records:
                if record.runtime != self.runtime:
                    raise InvalidAvailabilityTransition(
                        "capability belongs to another runtime or channel"
                    )
            self._data.capabilities = tuple(records)

        if event.name in {
            AvailabilityEvent.RUNTIME_MISSING,
            AvailabilityEvent.RUNTIME_UNAVAILABLE,
            AvailabilityEvent.RUNTIME_INCOMPATIBLE,
            AvailabilityEvent.CAPABILITY_PROBE_FAILED,
        }:
            failure = event.payload.get("failure")
            if not isinstance(failure, RuntimeFailure):
                raise InvalidAvailabilityTransition(
                    "failure event requires a RuntimeFailure payload"
                )
            self._data.failure = failure
