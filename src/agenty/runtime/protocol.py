"""Provider-neutral public protocol for RuntimeMachine.

This module defines facts shared across Agenty and runtime adapters. It does not
start a runtime, apply transitions, or contain vendor-specific configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, TypeAlias


class AvailabilityState(str, Enum):
    UNKNOWN = "unknown"
    PROBING = "probing"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    INCOMPATIBLE = "incompatible"
    CLOSED = "closed"


class ChannelMode(str, Enum):
    TRANSIENT_PROCESS = "transient_process"
    MANAGED_SERVER = "managed_server"
    REMOTE_SERVER = "remote_server"
    ACP = "acp"
    INTERACTIVE_WINDOW = "interactive_window"


class ChannelState(str, Enum):
    DETACHED = "detached"
    STARTING = "starting"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    FAILED = "failed"


class SessionState(str, Enum):
    NONE = "none"
    RESOLVING = "resolving"
    READY = "ready"
    BUSY = "busy"
    FORKING = "forking"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class TurnState(str, Enum):
    CREATED = "created"
    SUBMITTING = "submitting"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class AvailabilityEvent(str, Enum):
    PROBE_STARTED = "probe_started"
    RUNTIME_DETECTED = "runtime_detected"
    RUNTIME_MISSING = "runtime_missing"
    RUNTIME_INCOMPATIBLE = "runtime_incompatible"
    CAPABILITIES_RESOLVED = "capabilities_resolved"
    CAPABILITY_PROBE_FAILED = "capability_probe_failed"
    RUNTIME_DEGRADED = "runtime_degraded"
    RUNTIME_RECOVERED = "runtime_recovered"
    RUNTIME_LOST = "runtime_lost"
    RUNTIME_CLOSED = "runtime_closed"


class ChannelEvent(str, Enum):
    CHANNEL_STARTING = "channel_starting"
    CHANNEL_CONNECTING = "channel_connecting"
    CHANNEL_CONNECTED = "channel_connected"
    CHANNEL_DEGRADED = "channel_degraded"
    CHANNEL_FAILED = "channel_failed"
    CHANNEL_CONNECTION_LOST = "channel_connection_lost"
    CHANNEL_STOPPING = "channel_stopping"
    CHANNEL_DETACHED = "channel_detached"


class SessionEvent(str, Enum):
    SESSION_RESOLUTION_STARTED = "session_resolution_started"
    SESSION_RESOLVED = "session_resolved"
    SESSION_RESOLUTION_FAILED = "session_resolution_failed"
    SESSION_FORK_STARTED = "session_fork_started"
    SESSION_FORKED = "session_forked"
    SESSION_BECAME_BUSY = "session_became_busy"
    SESSION_BECAME_READY = "session_became_ready"
    SESSION_LOST = "session_lost"
    SESSION_CLOSE_STARTED = "session_close_started"
    SESSION_CLOSED = "session_closed"


class TurnEvent(str, Enum):
    TURN_CREATED = "turn_created"
    TURN_SUBMISSION_STARTED = "turn_submission_started"
    TURN_ACCEPTED = "turn_accepted"
    TURN_WAITING_FOR_INPUT = "turn_waiting_for_input"
    TURN_INPUT_SUPPLIED = "turn_input_supplied"
    TURN_WAITING_FOR_APPROVAL = "turn_waiting_for_approval"
    TURN_APPROVAL_RESOLVED = "turn_approval_resolved"
    TURN_SUCCEEDED = "turn_succeeded"
    TURN_FAILED = "turn_failed"
    TURN_CANCELLED = "turn_cancelled"
    TURN_TIMED_OUT = "turn_timed_out"


class OutputEvent(str, Enum):
    STEP_STARTED = "step_started"
    STEP_FINISHED = "step_finished"
    TEXT_EMITTED = "text_emitted"
    REASONING_EMITTED = "reasoning_emitted"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    USAGE_REPORTED = "usage_reported"
    RUNTIME_ERROR_EMITTED = "runtime_error_emitted"


RuntimeEventName: TypeAlias = (
    AvailabilityEvent | ChannelEvent | SessionEvent | TurnEvent | OutputEvent
)


@dataclass(frozen=True)
class RuntimeIdentity:
    """Identity and transport coordinates for one runtime instance."""

    runtime_id: str
    runtime_kind: str
    runtime_version: str | None = None
    channel: ChannelMode | None = None
    endpoint: str | None = None
    process_id: int | None = None


@dataclass(frozen=True)
class RuntimeEvent:
    """Normalized fact published across the RuntimeMachine boundary."""

    name: RuntimeEventName
    runtime: RuntimeIdentity
    correlation_id: str
    session_id: str | None = None
    turn_id: str | None = None
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    payload: Mapping[str, object] = field(default_factory=dict)
    raw_event: object | None = None


@dataclass(frozen=True)
class RuntimeSnapshot:
    """Read-only aggregate view; child machine states remain independent."""

    runtime: RuntimeIdentity
    availability: AvailabilityState = AvailabilityState.UNKNOWN
    channel: ChannelState = ChannelState.DETACHED
    session: SessionState = SessionState.NONE
    turn: TurnState | None = None
    session_id: str | None = None
    turn_id: str | None = None
    sequence: int = 0
    observed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

