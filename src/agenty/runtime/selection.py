"""Application-facing runtime type and exact-version selection state machine."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agenty.runtime.adapters import RuntimeAdapter
from agenty.runtime.machine import RuntimeProbeMachine
from agenty.runtime.protocol import (
    AvailabilityState,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeSnapshot,
    RuntimeTarget,
)


class RuntimeSelectionState(str, Enum):
    UNSELECTED = "unselected"
    RESOLVING = "resolving"
    SELECTED = "selected"
    REJECTED = "rejected"
    CLOSED = "closed"


class RuntimeSelectionEventName(str, Enum):
    SELECTION_STARTED = "runtime_selection_started"
    RUNTIME_SELECTED = "runtime_selected"
    RUNTIME_REJECTED = "runtime_rejected"
    SELECTION_CLEARED = "runtime_selection_cleared"
    SELECTION_CLOSED = "runtime_selection_closed"


class RuntimeSelectionEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: RuntimeSelectionEventName
    correlation_id: str
    target: RuntimeTarget | None = None
    snapshot: RuntimeSnapshot | None = None
    failure: RuntimeFailure | None = None

    @model_validator(mode="after")
    def validate_event_data(self) -> "RuntimeSelectionEvent":
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must not be empty")
        if self.name is RuntimeSelectionEventName.SELECTION_STARTED:
            if self.target is None:
                raise ValueError("selection_started requires target")
        if self.name is RuntimeSelectionEventName.RUNTIME_SELECTED:
            if self.target is None or self.snapshot is None:
                raise ValueError("runtime_selected requires target and snapshot")
        if self.name is RuntimeSelectionEventName.RUNTIME_REJECTED:
            if self.target is None or self.failure is None:
                raise ValueError("runtime_rejected requires target and failure")
        return self


class RuntimeSelectionStateData(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    state: RuntimeSelectionState = RuntimeSelectionState.UNSELECTED
    target: RuntimeTarget | None = None
    snapshot: RuntimeSnapshot | None = None
    failure: RuntimeFailure | None = None
    events: list[RuntimeSelectionEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_state_context(self) -> "RuntimeSelectionStateData":
        if self.state is RuntimeSelectionState.UNSELECTED and any(
            value is not None for value in (self.target, self.snapshot, self.failure)
        ):
            raise ValueError("unselected state cannot retain selection context")
        if self.state is RuntimeSelectionState.RESOLVING and self.target is None:
            raise ValueError("resolving state requires target")
        if self.state is RuntimeSelectionState.SELECTED:
            if self.target is None or self.snapshot is None:
                raise ValueError("selected state requires target and snapshot")
            if self.failure is not None:
                raise ValueError("selected state cannot retain failure")
        if self.state is RuntimeSelectionState.REJECTED:
            if self.target is None or self.failure is None:
                raise ValueError("rejected state requires target and failure")
        return self


class InvalidRuntimeSelection(RuntimeError):
    pass


AdapterFactory = Callable[[], RuntimeAdapter]


class RuntimeAdapterRegistry:
    """Exact `(runtime kind, adapter version)` to adapter factory registry."""

    def __init__(self) -> None:
        self._factories: dict[tuple[str, str], AdapterFactory] = {}

    def register(self, target: RuntimeTarget, factory: AdapterFactory) -> None:
        if target.key in self._factories:
            raise ValueError(f"adapter already registered for {target.key!r}")
        self._factories[target.key] = factory

    def resolve(self, target: RuntimeTarget) -> RuntimeAdapter | None:
        factory = self._factories.get(target.key)
        return None if factory is None else factory()

    def versions_for(self, runtime_kind: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                version
                for kind, version in self._factories
                if kind == runtime_kind
            )
        )


class RuntimeSelectionMachine:
    def __init__(
        self,
        registry: RuntimeAdapterRegistry,
        state_data: RuntimeSelectionStateData | None = None,
    ) -> None:
        self.registry = registry
        self._data = state_data or RuntimeSelectionStateData()

    @property
    def data(self) -> RuntimeSelectionStateData:
        return self._data

    @property
    def state(self) -> RuntimeSelectionState:
        return self._data.state

    @property
    def events(self) -> tuple[RuntimeSelectionEvent, ...]:
        return tuple(self._data.events)

    def select(
        self,
        target: RuntimeTarget,
        correlation_id: str,
    ) -> RuntimeSelectionStateData:
        if self.state not in {
            RuntimeSelectionState.UNSELECTED,
            RuntimeSelectionState.REJECTED,
        }:
            raise InvalidRuntimeSelection(
                f"cannot select runtime from {self.state.value!r}"
            )
        self._record(
            RuntimeSelectionEvent(
                name=RuntimeSelectionEventName.SELECTION_STARTED,
                correlation_id=correlation_id,
                target=target,
            )
        )

        try:
            adapter = self.registry.resolve(target)
        except Exception as exc:
            return self._reject(
                target,
                correlation_id,
                RuntimeFailure(
                    code=RuntimeFailureCode.INTERNAL,
                    message="runtime adapter factory raised an unexpected error",
                    details={
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                ),
            )
        if adapter is None:
            versions = self.registry.versions_for(target.runtime_kind)
            return self._reject(
                target,
                correlation_id,
                RuntimeFailure(
                    code=RuntimeFailureCode.ADAPTER_NOT_REGISTERED,
                    message="no adapter registered for exact runtime target",
                    details={
                        "runtime_kind": target.runtime_kind,
                        "runtime_version": target.runtime_version,
                        "registered_versions": versions,
                    },
                ),
            )

        try:
            adapter_kind = adapter.identity.runtime_kind
        except Exception as exc:
            return self._reject(
                target,
                correlation_id,
                RuntimeFailure(
                    code=RuntimeFailureCode.INTERNAL,
                    message="runtime adapter identity could not be read",
                    details={
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                ),
            )
        if adapter_kind != target.runtime_kind:
            return self._reject(
                target,
                correlation_id,
                RuntimeFailure(
                    code=RuntimeFailureCode.IDENTITY_MISMATCH,
                    message="registered adapter kind does not match target",
                    details={
                        "expected_kind": target.runtime_kind,
                        "actual_kind": adapter_kind,
                    },
                ),
            )

        snapshot = RuntimeProbeMachine(adapter).probe(correlation_id)
        if snapshot.availability is not AvailabilityState.AVAILABLE:
            failure = snapshot.failure or RuntimeFailure(
                code=RuntimeFailureCode.INTERNAL,
                message="runtime probe did not produce an available snapshot",
                details={"availability": snapshot.availability.value},
            )
            return self._reject(
                target,
                correlation_id,
                failure,
                snapshot,
            )

        actual = snapshot.runtime
        if (
            actual.runtime_kind != target.runtime_kind
            or actual.runtime_version != target.runtime_version
        ):
            return self._reject(
                target,
                correlation_id,
                RuntimeFailure(
                    code=RuntimeFailureCode.IDENTITY_MISMATCH,
                    message="detected runtime does not match selected target",
                    details={
                        "expected_kind": target.runtime_kind,
                        "expected_version": target.runtime_version,
                        "actual_kind": actual.runtime_kind,
                        "actual_version": actual.runtime_version,
                    },
                ),
                snapshot,
            )

        self._record(
            RuntimeSelectionEvent(
                name=RuntimeSelectionEventName.RUNTIME_SELECTED,
                correlation_id=correlation_id,
                target=target,
                snapshot=snapshot,
            )
        )
        return self.snapshot()

    def clear(self, correlation_id: str) -> RuntimeSelectionStateData:
        if self.state not in {
            RuntimeSelectionState.SELECTED,
            RuntimeSelectionState.REJECTED,
        }:
            raise InvalidRuntimeSelection(
                f"cannot clear runtime from {self.state.value!r}"
            )
        self._record(
            RuntimeSelectionEvent(
                name=RuntimeSelectionEventName.SELECTION_CLEARED,
                correlation_id=correlation_id,
                target=self._data.target,
            )
        )
        return self.snapshot()

    def close(self, correlation_id: str) -> RuntimeSelectionStateData:
        if self.state is RuntimeSelectionState.CLOSED:
            raise InvalidRuntimeSelection("runtime selection is already closed")
        self._record(
            RuntimeSelectionEvent(
                name=RuntimeSelectionEventName.SELECTION_CLOSED,
                correlation_id=correlation_id,
                target=self._data.target,
            )
        )
        return self.snapshot()

    def snapshot(self) -> RuntimeSelectionStateData:
        return self._data.model_copy(deep=True)

    def _reject(
        self,
        target: RuntimeTarget,
        correlation_id: str,
        failure: RuntimeFailure,
        snapshot: RuntimeSnapshot | None = None,
    ) -> RuntimeSelectionStateData:
        self._record(
            RuntimeSelectionEvent(
                name=RuntimeSelectionEventName.RUNTIME_REJECTED,
                correlation_id=correlation_id,
                target=target,
                snapshot=snapshot,
                failure=failure,
            )
        )
        return self.snapshot()

    def _record(self, event: RuntimeSelectionEvent) -> None:
        transitions = {
            (
                RuntimeSelectionState.UNSELECTED,
                RuntimeSelectionEventName.SELECTION_STARTED,
            ): RuntimeSelectionState.RESOLVING,
            (
                RuntimeSelectionState.REJECTED,
                RuntimeSelectionEventName.SELECTION_STARTED,
            ): RuntimeSelectionState.RESOLVING,
            (
                RuntimeSelectionState.RESOLVING,
                RuntimeSelectionEventName.RUNTIME_SELECTED,
            ): RuntimeSelectionState.SELECTED,
            (
                RuntimeSelectionState.RESOLVING,
                RuntimeSelectionEventName.RUNTIME_REJECTED,
            ): RuntimeSelectionState.REJECTED,
            (
                RuntimeSelectionState.SELECTED,
                RuntimeSelectionEventName.SELECTION_CLEARED,
            ): RuntimeSelectionState.UNSELECTED,
            (
                RuntimeSelectionState.REJECTED,
                RuntimeSelectionEventName.SELECTION_CLEARED,
            ): RuntimeSelectionState.UNSELECTED,
        }
        if event.name is RuntimeSelectionEventName.SELECTION_CLOSED:
            next_state = RuntimeSelectionState.CLOSED
        else:
            next_state = transitions.get((self.state, event.name))
            if next_state is None:
                raise InvalidRuntimeSelection(
                    f"cannot apply {event.name.value!r} from {self.state.value!r}"
                )

        target = self._data.target
        snapshot = self._data.snapshot
        failure = self._data.failure
        if event.name is RuntimeSelectionEventName.SELECTION_STARTED:
            target = event.target
            snapshot = None
            failure = None
        elif event.name is RuntimeSelectionEventName.RUNTIME_SELECTED:
            snapshot = event.snapshot
            failure = None
        elif event.name is RuntimeSelectionEventName.RUNTIME_REJECTED:
            snapshot = event.snapshot
            failure = event.failure
        elif event.name is RuntimeSelectionEventName.SELECTION_CLEARED:
            target = None
            snapshot = None
            failure = None

        self._data = RuntimeSelectionStateData(
            state=next_state,
            target=target,
            snapshot=snapshot,
            failure=failure,
            events=[*self._data.events, event],
        )
