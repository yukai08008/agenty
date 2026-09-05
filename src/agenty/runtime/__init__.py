"""Runtime state machine and adapter contracts."""

from agenty.runtime.availability import (
    AvailabilityMachine,
    InvalidAvailabilityTransition,
)
from agenty.runtime.machine import (
    InvalidRuntimeTransition as LegacyInvalidRuntimeTransition,
)
from agenty.runtime.machine import RuntimeMachine as LegacyProbeMachine
from agenty.runtime.models import (
    RuntimeCapability as LegacyRuntimeCapability,
    RuntimeEvent as LegacyRuntimeEvent,
    RuntimeEventType as LegacyRuntimeEventType,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeInfo as LegacyRuntimeInfo,
    RuntimeSnapshot as LegacyRuntimeSnapshot,
    RuntimeState as LegacyRuntimeState,
)
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
    "CapabilityRecord",
    "CapabilitySupport",
    "ChannelEvent",
    "ChannelMode",
    "ChannelState",
    "EvidenceLevel",
    "InvalidAvailabilityTransition",
    "LegacyInvalidRuntimeTransition",
    "LegacyProbeMachine",
    "LegacyRuntimeCapability",
    "LegacyRuntimeEvent",
    "LegacyRuntimeEventType",
    "LegacyRuntimeInfo",
    "LegacyRuntimeSnapshot",
    "LegacyRuntimeState",
    "OutputEvent",
    "RuntimeEvent",
    "RuntimeFailure",
    "RuntimeFailureCode",
    "RuntimeIdentity",
    "RuntimeSnapshot",
    "SessionEvent",
    "SessionState",
    "TurnEvent",
    "TurnState",
]
