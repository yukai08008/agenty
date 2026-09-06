"""Provider-neutral public protocol for RuntimeMachine.

This module defines facts shared across Agenty and runtime adapters. It does not
start a runtime, apply transitions, or contain vendor-specific configuration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    RUNTIME_UNAVAILABLE = "runtime_unavailable"
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


class CapabilitySupport(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


class EvidenceLevel(str, Enum):
    UNKNOWN = "unknown"
    ADVERTISED = "advertised"
    SOURCE_CONFIRMED = "source_confirmed"
    PROBE_VERIFIED = "probe_verified"
    INTEGRATION_VERIFIED = "integration_verified"
    LIVE_VERIFIED = "live_verified"


class RuntimeFailureCode(str, Enum):
    ADAPTER_NOT_REGISTERED = "runtime_adapter_not_registered"
    IDENTITY_MISMATCH = "runtime_identity_mismatch"
    NOT_FOUND = "runtime_not_found"
    PROBE_TIMEOUT = "runtime_probe_timeout"
    PROBE_EXIT = "runtime_probe_exit"
    INVALID_VERSION = "runtime_invalid_version"
    UNSUPPORTED_VERSION = "runtime_unsupported_version"
    INTERNAL = "runtime_internal_error"
    TURN_REJECTED = "turn_rejected"
    TURN_FAILED = "turn_failed"
    TURN_TIMEOUT = "turn_timeout"
    INVALID_OUTPUT = "runtime_invalid_output"


RuntimeEventName: TypeAlias = (
    AvailabilityEvent | ChannelEvent | SessionEvent | TurnEvent | OutputEvent
)


class RuntimeTarget(BaseModel):
    """Application-selected runtime kind and exact adapter version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime_kind: str
    runtime_version: str

    @field_validator("runtime_kind", "runtime_version")
    @classmethod
    def validate_target_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_exact_version(self) -> "RuntimeTarget":
        if any(marker in self.runtime_version for marker in "<>=*^~"):
            raise ValueError("runtime_version must be an exact version")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return (self.runtime_kind, self.runtime_version)


class RuntimeIdentity(BaseModel):
    """Identity and transport coordinates for one runtime instance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime_id: str
    runtime_kind: str
    runtime_version: str | None = None
    executable: str | None = None
    channel: ChannelMode | None = None
    endpoint: str | None = None
    process_id: int | None = None

    @field_validator("runtime_id", "runtime_kind")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("runtime_version", "executable", "endpoint")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("process_id")
    @classmethod
    def validate_process_id(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("process_id must be positive")
        return value


class CapabilityRecord(BaseModel):
    """Version- and channel-scoped capability claim with evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    capability: str
    runtime: RuntimeIdentity
    support: CapabilitySupport
    evidence: EvidenceLevel
    evidence_source: str | None = None
    constraints: tuple[str, ...] = ()

    @field_validator("capability")
    @classmethod
    def validate_capability(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("capability must not be empty")
        return value

    @model_validator(mode="after")
    def validate_claim(self) -> "CapabilityRecord":
        if not self.runtime.runtime_version:
            raise ValueError("capability requires a runtime version")
        if self.runtime.channel is None:
            raise ValueError("capability requires a channel")
        if self.evidence is not EvidenceLevel.UNKNOWN and not self.evidence_source:
            raise ValueError("known evidence requires an evidence source")
        if (
            self.support is not CapabilitySupport.UNKNOWN
            and self.evidence is EvidenceLevel.UNKNOWN
        ):
            raise ValueError("a support claim requires evidence")
        if (
            self.support is CapabilitySupport.CONDITIONAL
            and not self.constraints
        ):
            raise ValueError("conditional support requires constraints")
        return self

    @property
    def key(self) -> tuple[str, str, ChannelMode, str]:
        version = self.runtime.runtime_version
        channel = self.runtime.channel
        assert version is not None
        assert channel is not None
        return (
            self.runtime.runtime_kind,
            version,
            channel,
            self.capability,
        )


class RuntimeFailure(BaseModel):
    """Structured failure safe to expose across the runtime boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: RuntimeFailureCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class RuntimeTurnRequest(BaseModel):
    """Provider-neutral command for one new-session runtime turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    turn_id: str
    correlation_id: str
    prompt: str
    working_directory: str
    model: str | None = None
    effort: str | None = None

    @field_validator(
        "turn_id", "correlation_id", "working_directory", "model", "effort"
    )
    @classmethod
    def validate_request_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value


class RuntimeEvent(BaseModel):
    """Normalized fact published across the RuntimeMachine boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: RuntimeEventName
    runtime: RuntimeIdentity
    correlation_id: str
    session_id: str | None = None
    turn_id: str | None = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    raw_event: Any | None = None


class RuntimeSnapshot(BaseModel):
    """Read-only aggregate view; child machine states remain independent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime: RuntimeIdentity
    availability: AvailabilityState = AvailabilityState.UNKNOWN
    channel: ChannelState = ChannelState.DETACHED
    session: SessionState = SessionState.NONE
    turn: TurnState | None = None
    session_id: str | None = None
    turn_id: str | None = None
    capabilities: tuple[CapabilityRecord, ...] = Field(default_factory=tuple)
    failure: RuntimeFailure | None = None
    sequence: int = 0
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
