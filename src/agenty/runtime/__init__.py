"""Runtime state machine and adapter contracts."""

from agenty.runtime.availability import (
    AvailabilityMachine,
    AvailabilityStateData,
    InvalidAvailabilityTransition,
)
from agenty.runtime.machine import RuntimeProbeMachine
from agenty.runtime.protocol import (
    AvailabilityEvent,
    AvailabilityState,
    CapabilityRecord,
    CapabilitySupport,
    ChannelEvent,
    ChannelMode,
    ChannelState,
    EvidenceLevel,
    OutputEvent,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeSnapshot,
    SessionEvent,
    SessionState,
    TurnEvent,
    TurnState,
)

__all__ = [
    "AvailabilityEvent",
    "AvailabilityMachine",
    "AvailabilityState",
    "AvailabilityStateData",
    "CapabilityRecord",
    "CapabilitySupport",
    "ChannelEvent",
    "ChannelMode",
    "ChannelState",
    "EvidenceLevel",
    "InvalidAvailabilityTransition",
    "OutputEvent",
    "RuntimeEvent",
    "RuntimeFailure",
    "RuntimeFailureCode",
    "RuntimeIdentity",
    "RuntimeProbeMachine",
    "RuntimeSnapshot",
    "SessionEvent",
    "SessionState",
    "TurnEvent",
    "TurnState",
]
