"""Provider-neutral adapter boundary for runtime probing."""

from __future__ import annotations

from typing import Protocol

from agenty.runtime.protocol import (
    AvailabilityEvent,
    CapabilityRecord,
    RuntimeFailure,
    RuntimeIdentity,
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
