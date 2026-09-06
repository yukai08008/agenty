"""Provider-neutral adapter boundary for runtime probing."""

from __future__ import annotations

from collections.abc import Iterator
from threading import Event, Lock
from typing import Protocol

from agenty.runtime.protocol import (
    AvailabilityEvent,
    CapabilityRecord,
    RuntimeApprovalDecision,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeIdentity,
    RuntimeModelCatalog,
    RuntimeTurnRequest,
)


class RuntimeAdapterError(RuntimeError):
    def __init__(
        self,
        event: AvailabilityEvent,
        failure: RuntimeFailure,
    ) -> None:
        self.event = event
        self.failure = failure
        super().__init__(failure.message)


class RuntimeTurnAdapterError(RuntimeError):
    def __init__(
        self,
        failure: RuntimeFailure,
        *,
        timed_out: bool = False,
        cancelled: bool = False,
    ) -> None:
        self.failure = failure
        self.timed_out = timed_out
        self.cancelled = cancelled
        super().__init__(failure.message)


class RuntimeModelAdapterError(RuntimeError):
    def __init__(self, failure: RuntimeFailure) -> None:
        self.failure = failure
        super().__init__(failure.message)


class RuntimeAdapter(Protocol):
    """Runtime-specific observations used by the generic probe machine."""

    @property
    def identity(self) -> RuntimeIdentity:
        ...

    def detect(self) -> RuntimeIdentity:
        ...

    def probe_capabilities(
        self,
        runtime: RuntimeIdentity,
    ) -> tuple[CapabilityRecord, ...]:
        ...


class RuntimeTurnAdapter(Protocol):
    """Runtime-specific execution that yields normalized public events."""

    def iter_turn_events(
        self,
        runtime: RuntimeIdentity,
        request: RuntimeTurnRequest,
        control: RuntimeTurnControl,
    ) -> Iterator[RuntimeEvent]:
        ...

    def reply_approval(self, decision: RuntimeApprovalDecision) -> None:
        ...


class RuntimeTurnControl:
    """Process-local cancellation signal shared by a runner and adapter."""

    def __init__(self) -> None:
        self._cancelled = Event()
        self._lock = Lock()
        self._actor: str | None = None

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    @property
    def actor(self) -> str | None:
        with self._lock:
            return self._actor

    def cancel(self, actor: str) -> None:
        with self._lock:
            self._actor = actor
            self._cancelled.set()


class RuntimeModelAdapter(Protocol):
    """Runtime-specific discovery of version-scoped model choices."""

    def probe_model_catalog(
        self,
        runtime: RuntimeIdentity,
    ) -> RuntimeModelCatalog:
        ...
