"""Provider-neutral adapter boundary for runtime probing."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from agenty.runtime.protocol import (
    AvailabilityEvent,
    CapabilityRecord,
    RuntimeFailure,
    RuntimeEvent,
    RuntimeIdentity,
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
    ) -> None:
        self.failure = failure
        self.timed_out = timed_out
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
    ) -> Iterator[RuntimeEvent]:
        ...
