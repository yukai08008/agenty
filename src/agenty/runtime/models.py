"""Provider-neutral models for the Runtime Machine."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RuntimeState(str, Enum):
    UNKNOWN = "unknown"
    PROBING = "probing"
    READY = "ready"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    CLOSED = "closed"


class RuntimeEventType(str, Enum):
    PROBE_REQUESTED = "probe.requested"
    PROBE_SUCCEEDED = "probe.succeeded"
    PROBE_FAILED = "probe.failed"
    FAULT_DETECTED = "fault.detected"
    CLOSE_REQUESTED = "close.requested"


class RuntimeCapability(str, Enum):
    MODELS = "models"
    EFFORT_LEVELS = "effort_levels"
    SESSIONS = "sessions"
    RESUME = "resume"
    FORK = "fork"
    INTERACTIVE_WINDOW = "interactive_window"
    STRUCTURED_OUTPUT = "structured_output"
    ATTACHMENTS = "attachments"
    APPROVALS = "approvals"
    INTERRUPT = "interrupt"


class RuntimeFailureCode(str, Enum):
    NOT_FOUND = "runtime_not_found"
    PROBE_TIMEOUT = "runtime_probe_timeout"
    PROBE_EXIT = "runtime_probe_exit"
    INVALID_VERSION = "runtime_invalid_version"
    INTERNAL = "runtime_internal_error"


class RuntimeFailure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: RuntimeFailureCode
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class RuntimeInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime_id: str
    kind: str
    version: str
    executable: str
    capabilities: frozenset[RuntimeCapability]
    evidence: dict[str, str] = Field(default_factory=dict)


class RuntimeEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: RuntimeEventType
    from_state: RuntimeState
    to_state: RuntimeState
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RuntimeSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    state: RuntimeState
    info: RuntimeInfo | None
    failure: RuntimeFailure | None
    events: tuple[RuntimeEvent, ...]
