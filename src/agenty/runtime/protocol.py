"""Provider-neutral public protocol for RuntimeMachine.

This module defines facts shared across Agenty and runtime adapters. It does not
start a runtime, apply transitions, or contain vendor-specific configuration.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path, PurePosixPath
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


class InteractionEvent(str, Enum):
    INTERACTION_POLICY_APPLIED = "interaction_policy_applied"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_DECIDED = "approval_decided"
    TURN_CANCEL_REQUESTED = "turn_cancel_requested"


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
    SESSION_NOT_FOUND = "runtime_session_not_found"
    ENVIRONMENT_MISMATCH = "runtime_environment_mismatch"
    SESSION_ID_MISMATCH = "runtime_session_id_mismatch"
    MODEL_NOT_FOUND = "runtime_model_not_found"
    EFFORT_UNSUPPORTED = "runtime_effort_unsupported"
    MODEL_CATALOG_INVALID = "runtime_model_catalog_invalid"
    INTERACTION_UNSUPPORTED = "runtime_interaction_unsupported"
    RATE_LIMITED = "runtime_rate_limited"
    QUOTA_EXHAUSTED = "runtime_quota_exhausted"
    AUTHENTICATION_FAILED = "runtime_authentication_failed"
    MODEL_UNAVAILABLE = "runtime_model_unavailable"
    RUNTIME_CRASH = "runtime_crash"


RuntimeEventName: TypeAlias = (
    AvailabilityEvent
    | ChannelEvent
    | SessionEvent
    | TurnEvent
    | InteractionEvent
    | OutputEvent
)

INTERACTION_APPROVAL_CAPABILITY = "interaction.approval_roundtrip"
INTERACTION_AUTO_APPROVE_CAPABILITY = "interaction.auto_approve"
TURN_CANCEL_CAPABILITY = "turn.cancel"


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
    retryable: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("details")
    @classmethod
    def validate_details(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(value, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("failure details must be strict JSON") from exc
        return value


class SessionOpenMode(str, Enum):
    NEW = "new"
    RESUME = "resume"


class ProjectEnvironment(BaseModel):
    """Application-owned identity for the project state behind a session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    environment_id: str
    project_id: str
    working_directory: str
    revision: str | None = None

    @field_validator("environment_id", "project_id", "revision")
    @classmethod
    def validate_environment_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("working_directory")
    @classmethod
    def normalize_environment_directory(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("working_directory must not be empty")
        return str(Path(value).expanduser().resolve())


class RuntimeSessionRequest(BaseModel):
    """Provider-neutral request to create or resume a runtime session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: SessionOpenMode
    correlation_id: str
    environment: ProjectEnvironment
    session_id: str | None = None

    @field_validator("correlation_id", "session_id")
    @classmethod
    def validate_session_request_text(
        cls, value: str | None
    ) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_mode(self) -> "RuntimeSessionRequest":
        if self.mode is SessionOpenMode.NEW and self.session_id is not None:
            raise ValueError("new session request must not include session_id")
        if self.mode is SessionOpenMode.RESUME and self.session_id is None:
            raise ValueError("resume session request requires session_id")
        return self


class RuntimeSessionBinding(BaseModel):
    """Auditable lock between runtime lineage and project environment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime: RuntimeIdentity
    session_id: str
    environment: ProjectEnvironment
    origin: SessionOpenMode
    parent_session_id: str | None = None

    @field_validator("session_id", "parent_session_id")
    @classmethod
    def validate_binding_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_runtime_scope(self) -> "RuntimeSessionBinding":
        if self.runtime.runtime_version is None:
            raise ValueError("session binding requires runtime version")
        if self.runtime.channel is None:
            raise ValueError("session binding requires runtime channel")
        if self.parent_session_id == self.session_id:
            raise ValueError("session cannot be its own parent")
        return self


class RuntimeModelRef(BaseModel):
    """Provider-neutral identity for a model exposed by a runtime."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_type: str
    provider_id: str
    model_id: str

    @field_validator("model_type", "provider_id", "model_id")
    @classmethod
    def validate_model_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_components(self) -> "RuntimeModelRef":
        if "/" in self.provider_id or "/" in self.model_id:
            raise ValueError("provider_id and model_id must be unqualified")
        return self

    @property
    def qualified_id(self) -> str:
        return f"{self.provider_id}/{self.model_id}"


class RuntimeModelSelection(BaseModel):
    """Desired or effective model configuration for one turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: RuntimeModelRef
    effort: str | None = None

    @field_validator("effort")
    @classmethod
    def validate_effort(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("effort must not be empty")
        return value


class RuntimeModelDescriptor(BaseModel):
    """One model and the effort values observed for a runtime version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime: RuntimeIdentity
    model: RuntimeModelRef
    display_name: str | None = None
    supported_efforts: tuple[str, ...] = ()
    evidence: EvidenceLevel
    evidence_source: str

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("display_name must not be empty")
        return value

    @field_validator("supported_efforts")
    @classmethod
    def validate_supported_efforts(
        cls, values: tuple[str, ...]
    ) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("supported effort must not be empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("supported efforts must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_evidence(self) -> "RuntimeModelDescriptor":
        if self.runtime.runtime_version is None or self.runtime.channel is None:
            raise ValueError("model descriptor requires versioned runtime channel")
        if self.evidence is EvidenceLevel.UNKNOWN:
            raise ValueError("model descriptor requires observed evidence")
        if not self.evidence_source.strip():
            raise ValueError("evidence_source must not be empty")
        return self


class RuntimeModelCatalog(BaseModel):
    """Version-scoped model choices discovered from one runtime instance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime: RuntimeIdentity
    models: tuple[RuntimeModelDescriptor, ...] = ()

    @model_validator(mode="after")
    def validate_catalog(self) -> "RuntimeModelCatalog":
        if self.runtime.runtime_version is None or self.runtime.channel is None:
            raise ValueError("model catalog requires versioned runtime channel")
        identities: set[tuple[str, str, str]] = set()
        for descriptor in self.models:
            if descriptor.runtime != self.runtime:
                raise ValueError("model descriptor runtime does not match catalog")
            key = (
                descriptor.model.model_type,
                descriptor.model.provider_id,
                descriptor.model.model_id,
            )
            if key in identities:
                raise ValueError("model identities must be unique")
            identities.add(key)
        return self

    def find(self, model: RuntimeModelRef) -> RuntimeModelDescriptor | None:
        return next(
            (item for item in self.models if item.model == model),
            None,
        )


class RuntimeModelBinding(BaseModel):
    """Validated lock between a selection and version-scoped model evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime: RuntimeIdentity
    selection: RuntimeModelSelection
    descriptor: RuntimeModelDescriptor

    @model_validator(mode="after")
    def validate_binding(self) -> "RuntimeModelBinding":
        if self.descriptor.runtime != self.runtime:
            raise ValueError("model descriptor belongs to another runtime")
        if self.descriptor.model != self.selection.model:
            raise ValueError("model descriptor does not match selection")
        if (
            self.selection.effort is not None
            and self.selection.effort not in self.descriptor.supported_efforts
        ):
            raise ValueError("effort is not supported by model descriptor")
        return self


class InteractionPolicyMode(str, Enum):
    ASK = "ask"
    AUTO_APPROVE = "auto_approve"
    AUTO_REJECT = "auto_reject"
    DENY_BY_DEFAULT = "deny_by_default"


class ApprovalOutcome(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class RuntimeInteractionPolicy(BaseModel):
    """Application-selected permission behavior for one turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: InteractionPolicyMode = InteractionPolicyMode.DENY_BY_DEFAULT


class RuntimeApprovalRequest(BaseModel):
    """Provider-neutral permission request emitted during a turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str
    permission: str
    description: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("request_id", "permission", "description")
    @classmethod
    def validate_approval_request_text(
        cls, value: str | None
    ) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class RuntimeApprovalDecision(BaseModel):
    """Auditable automatic or human resolution of one permission request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str
    outcome: ApprovalOutcome
    actor: str
    automatic: bool
    decided_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("request_id", "actor")
    @classmethod
    def validate_approval_decision_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class RuntimeUsage(BaseModel):
    """Aggregated token and cost observations for one turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost: Decimal = Field(default=Decimal(0), ge=0)
    currency: str = "USD"
    provider_references: tuple[str, ...] = ()

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("currency must not be empty")
        return value

    @model_validator(mode="after")
    def validate_total(self) -> "RuntimeUsage":
        observed = (
            self.input_tokens
            + self.output_tokens
            + self.reasoning_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )
        if self.total_tokens == 0 and observed:
            object.__setattr__(self, "total_tokens", observed)
        elif self.total_tokens != observed:
            raise ValueError("total_tokens must equal the observed token sum")
        return self


class RuntimeArtifact(BaseModel):
    """One regular file whose content differs from the pre-turn snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256: str
    producer: str

    @field_validator("path", "media_type", "sha256", "producer")
    @classmethod
    def validate_artifact_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_artifact(self) -> "RuntimeArtifact":
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts or "\\" in self.path:
            raise ValueError("artifact path must stay relative to its root")
        if len(self.sha256) != 64 or any(
            character not in "0123456789abcdef"
            for character in self.sha256.lower()
        ):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        return self


class ArtifactManifest(BaseModel):
    """Immutable, scoped observation of regular-file content changes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    root_directory: str
    artifacts: tuple[RuntimeArtifact, ...] = ()
    scan_complete: bool = True
    limitations: tuple[str, ...] = (
        "deletions, symlinks, and metadata-only changes are not represented",
        "producer attribution is not inferred from filesystem changes",
    )

    @field_validator("root_directory")
    @classmethod
    def validate_root_directory(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("root_directory must not be empty")
        return value

    @model_validator(mode="after")
    def validate_unique_paths(self) -> "ArtifactManifest":
        paths = [artifact.path for artifact in self.artifacts]
        if len(paths) != len(set(paths)):
            raise ValueError("artifact paths must be unique")
        return self


class EventLogRef(BaseModel):
    """Locations and digests for normalized and raw event evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    normalized_path: str
    normalized_sha256: str
    normalized_event_count: int = Field(ge=0)
    raw_path: str
    raw_sha256: str
    raw_event_count: int = Field(ge=0)
    format: str = "jsonl"

    @field_validator(
        "normalized_path",
        "normalized_sha256",
        "raw_path",
        "raw_sha256",
        "format",
    )
    @classmethod
    def validate_log_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("event log value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_log_reference(self) -> "EventLogRef":
        for digest in (self.normalized_sha256, self.raw_sha256):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef"
                for character in digest.lower()
            ):
                raise ValueError("event log digest must be hexadecimal sha256")
        if self.format != "jsonl":
            raise ValueError("event log format must be jsonl")
        return self


class TurnResult(BaseModel):
    """Immutable auditable result returned for one terminal turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime: RuntimeIdentity
    turn_id: str
    correlation_id: str
    request: RuntimeTurnRequest
    state: TurnState
    session_id: str | None = None
    output_text: str = ""
    usage: RuntimeUsage = Field(default_factory=RuntimeUsage)
    failure: RuntimeFailure | None = None
    artifacts: ArtifactManifest
    event_log: EventLogRef
    events: tuple[RuntimeEvent, ...] = ()

    @model_validator(mode="after")
    def validate_terminal_result(self) -> "TurnResult":
        if self.state not in {
            TurnState.SUCCEEDED,
            TurnState.FAILED,
            TurnState.CANCELLED,
            TurnState.TIMED_OUT,
        }:
            raise ValueError("turn result requires a terminal state")
        if self.state in {TurnState.FAILED, TurnState.TIMED_OUT}:
            if self.failure is None:
                raise ValueError("failed turn result requires failure")
        elif self.failure is not None:
            raise ValueError("successful or cancelled result cannot hold failure")
        if (
            self.turn_id != self.request.turn_id
            or self.correlation_id != self.request.correlation_id
        ):
            raise ValueError("turn result context must match its request")
        if self.artifacts.root_directory != self.request.working_directory:
            raise ValueError("artifact root must match the request working directory")
        if self.event_log.normalized_event_count != len(self.events):
            raise ValueError("normalized event count must match result events")
        expected_sequences = list(range(1, len(self.events) + 1))
        if [event.sequence for event in self.events] != expected_sequences:
            raise ValueError("result event sequence must be contiguous")
        for event in self.events:
            if (
                event.runtime != self.runtime
                or event.turn_id != self.turn_id
                or event.correlation_id != self.correlation_id
                or (
                    event.session_id is not None
                    and event.session_id != self.session_id
                )
            ):
                raise ValueError("result event context must match the turn result")
        if not self.events:
            raise ValueError("turn result requires an event history")
        terminal_events = {
            TurnState.SUCCEEDED: TurnEvent.TURN_SUCCEEDED,
            TurnState.FAILED: TurnEvent.TURN_FAILED,
            TurnState.CANCELLED: TurnEvent.TURN_CANCELLED,
            TurnState.TIMED_OUT: TurnEvent.TURN_TIMED_OUT,
        }
        terminal = self.events[-1]
        if terminal.name is not terminal_events[self.state]:
            raise ValueError("turn result state must match its terminal event")
        terminal_failure = terminal.payload.get("failure")
        if (
            self.failure is not None
            and RuntimeFailure.model_validate(terminal_failure) != self.failure
        ):
            raise ValueError("turn result failure must match its terminal event")
        expected_output = "".join(
            str(event.payload.get("text", ""))
            for event in self.events
            if event.name is OutputEvent.TEXT_EMITTED
        )
        if self.output_text != expected_output:
            raise ValueError("turn result output must match its events")
        totals = {
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        }
        cost = Decimal(0)
        references = []
        for event in self.events:
            if event.name is not OutputEvent.USAGE_REPORTED:
                continue
            for field in totals:
                totals[field] += event.payload.get(field, 0)
            cost += Decimal(str(event.payload.get("cost", 0)))
            reference = event.payload.get("provider_reference")
            if isinstance(reference, str) and reference not in references:
                references.append(reference)
        expected_usage = RuntimeUsage(
            **totals,
            total_tokens=sum(totals.values()),
            cost=cost,
            provider_references=tuple(references),
        )
        if self.usage != expected_usage:
            raise ValueError("turn result usage must match its events")
        return self


class RuntimeTurnRequest(BaseModel):
    """Provider-neutral command for one runtime turn."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    turn_id: str
    correlation_id: str
    prompt: str
    working_directory: str
    model: RuntimeModelBinding | None = None
    session: RuntimeSessionBinding | None = None
    interaction: RuntimeInteractionPolicy = Field(
        default_factory=RuntimeInteractionPolicy
    )

    @field_validator("turn_id", "correlation_id")
    @classmethod
    def validate_request_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("working_directory")
    @classmethod
    def normalize_working_directory(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("working_directory must not be empty")
        return str(Path(value).expanduser().resolve())

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_session_environment(self) -> "RuntimeTurnRequest":
        if (
            self.session is not None
            and self.working_directory
            != self.session.environment.working_directory
        ):
            raise ValueError(
                "turn working_directory must match the bound environment"
            )
        return self


class RuntimeEvent(BaseModel):
    """Normalized fact published across the RuntimeMachine boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: RuntimeEventName
    runtime: RuntimeIdentity
    correlation_id: str
    session_id: str | None = None
    turn_id: str | None = None
    sequence: int | None = Field(default=None, ge=1)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    source_reference: str | None = None
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
