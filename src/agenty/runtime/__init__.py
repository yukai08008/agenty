"""Runtime state machine and adapter contracts."""

from agenty.runtime.machine import InvalidRuntimeTransition, RuntimeMachine
from agenty.runtime.models import (
    RuntimeCapability,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeInfo,
    RuntimeSnapshot,
    RuntimeState,
)
from agenty.runtime.protocol import (
    AvailabilityEvent,
    AvailabilityState,
    ChannelEvent,
    ChannelMode,
    ChannelState,
    OutputEvent,
    RuntimeIdentity,
    SessionEvent,
    SessionState,
    TurnEvent,
    TurnState,
)

__all__ = [
    "InvalidRuntimeTransition",
    "AvailabilityEvent",
    "AvailabilityState",
    "ChannelEvent",
    "ChannelMode",
    "ChannelState",
    "OutputEvent",
    "RuntimeCapability",
    "RuntimeEvent",
    "RuntimeEventType",
    "RuntimeFailure",
    "RuntimeFailureCode",
    "RuntimeInfo",
    "RuntimeIdentity",
    "RuntimeMachine",
    "RuntimeSnapshot",
    "RuntimeState",
    "SessionEvent",
    "SessionState",
    "TurnEvent",
    "TurnState",
]
