"""Runtime-neutral model and effort selection state machine."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agenty.runtime.protocol import (
    EvidenceLevel,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeModelBinding,
    RuntimeModelCatalog,
    RuntimeModelSelection,
)


class ModelSelectionState(str, Enum):
    UNCONFIGURED = "unconfigured"
    VALIDATING = "validating"
    CONFIGURED = "configured"
    REJECTED = "rejected"


class ModelSelectionEventName(str, Enum):
    SELECTION_REQUESTED = "model_selection_requested"
    SELECTION_CONFIGURED = "model_selection_configured"
    SELECTION_REJECTED = "model_selection_rejected"
    EFFECTIVE_REPORTED = "model_effective_reported"
    SELECTION_CLEARED = "model_selection_cleared"


class ModelSelectionEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: ModelSelectionEventName
    correlation_id: str
    desired: RuntimeModelSelection | None = None
    binding: RuntimeModelBinding | None = None
    effective: RuntimeModelSelection | None = None
    evidence: EvidenceLevel | None = None
    evidence_source: str | None = None
    failure: RuntimeFailure | None = None

    @model_validator(mode="after")
    def validate_event(self) -> ModelSelectionEvent:
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must not be empty")
        if self.name in {
            ModelSelectionEventName.SELECTION_REQUESTED,
        } and self.desired is None:
            raise ValueError("selection event requires desired configuration")
        if (
            self.name is ModelSelectionEventName.SELECTION_CONFIGURED
            and (self.desired is None or self.binding is None)
        ):
            raise ValueError(
                "configured selection requires desired and binding"
            )
        if (
            self.name is ModelSelectionEventName.SELECTION_REJECTED
            and (self.desired is None or self.failure is None)
        ):
            raise ValueError("rejected selection requires desired and failure")
        if self.name is ModelSelectionEventName.EFFECTIVE_REPORTED:
            if (
                self.effective is None
                or self.evidence is None
                or not self.evidence_source
            ):
                raise ValueError(
                    "effective report requires selection and evidence"
                )
            if self.evidence is EvidenceLevel.UNKNOWN:
                raise ValueError("effective report requires known evidence")
            if self.evidence not in {
                EvidenceLevel.INTEGRATION_VERIFIED,
                EvidenceLevel.LIVE_VERIFIED,
            }:
                raise ValueError(
                    "effective report requires execution-level evidence"
                )
        return self


class ModelSelectionStateData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime: RuntimeIdentity
    state: ModelSelectionState = ModelSelectionState.UNCONFIGURED
    desired: RuntimeModelSelection | None = None
    binding: RuntimeModelBinding | None = None
    effective: RuntimeModelSelection | None = None
    effective_evidence: EvidenceLevel | None = None
    effective_evidence_source: str | None = None
    failure: RuntimeFailure | None = None
    events: tuple[ModelSelectionEvent, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_state(self) -> ModelSelectionStateData:
        if self.state is ModelSelectionState.UNCONFIGURED:
            if any(
                value is not None
                for value in (
                    self.desired,
                    self.binding,
                    self.effective,
                    self.effective_evidence,
                    self.effective_evidence_source,
                    self.failure,
                )
            ):
                raise ValueError("unconfigured state cannot retain selection")
        elif self.state is ModelSelectionState.VALIDATING:
            if self.desired is None or any(
                value is not None
                for value in (
                    self.binding,
                    self.effective,
                    self.effective_evidence,
                    self.effective_evidence_source,
                    self.failure,
                )
            ):
                raise ValueError(
                    "validating state requires only desired selection"
                )
        elif self.state is ModelSelectionState.CONFIGURED:
            if (
                self.desired is None
                or self.binding is None
                or self.failure is not None
            ):
                raise ValueError("configured state requires desired without failure")
        elif (
            self.state is ModelSelectionState.REJECTED
            and (
                self.desired is None
                or self.failure is None
                or any(
                    value is not None
                    for value in (
                        self.binding,
                        self.effective,
                        self.effective_evidence,
                        self.effective_evidence_source,
                    )
                )
            )
        ):
            raise ValueError(
                "rejected state requires only desired and failure"
            )
        if self.effective is None and any(
            value is not None
            for value in (
                self.effective_evidence,
                self.effective_evidence_source,
            )
        ):
            raise ValueError("effective evidence requires effective selection")
        if self.effective is not None and (
            self.effective_evidence is None
            or not self.effective_evidence_source
        ):
            raise ValueError("effective selection requires evidence")
        return self


class InvalidModelSelection(RuntimeError):
    pass


class RuntimeModelSelectionMachine:
    def __init__(
        self,
        runtime: RuntimeIdentity,
        state_data: ModelSelectionStateData | None = None,
    ) -> None:
        if state_data is not None and state_data.runtime != runtime:
            raise ValueError("state runtime does not match machine runtime")
        self._data = state_data or ModelSelectionStateData(runtime=runtime)

    @property
    def data(self) -> ModelSelectionStateData:
        return self._data.model_copy(deep=True)

    def configure(
        self,
        desired: RuntimeModelSelection,
        catalog: RuntimeModelCatalog,
        correlation_id: str,
    ) -> ModelSelectionStateData:
        if self._data.state not in {
            ModelSelectionState.UNCONFIGURED,
            ModelSelectionState.REJECTED,
        }:
            raise InvalidModelSelection(
                f"cannot configure model from {self._data.state.value}"
            )
        previous_events = self._data.events
        requested = ModelSelectionEvent(
            name=ModelSelectionEventName.SELECTION_REQUESTED,
            correlation_id=correlation_id,
            desired=desired,
        )
        self._data = ModelSelectionStateData(
            runtime=self._data.runtime,
            state=ModelSelectionState.VALIDATING,
            desired=desired,
            events=(*previous_events, requested),
        )

        failure = self._validate_selection(desired, catalog)
        if failure is not None:
            rejected = ModelSelectionEvent(
                name=ModelSelectionEventName.SELECTION_REJECTED,
                correlation_id=correlation_id,
                desired=desired,
                failure=failure,
            )
            self._data = ModelSelectionStateData(
                runtime=self._data.runtime,
                state=ModelSelectionState.REJECTED,
                desired=desired,
                failure=failure,
                events=(*self._data.events, rejected),
            )
            return self.data

        descriptor = catalog.find(desired.model)
        assert descriptor is not None
        binding = RuntimeModelBinding(
            runtime=self._data.runtime,
            selection=desired,
            descriptor=descriptor,
        )
        configured = ModelSelectionEvent(
            name=ModelSelectionEventName.SELECTION_CONFIGURED,
            correlation_id=correlation_id,
            desired=desired,
            binding=binding,
        )
        self._data = ModelSelectionStateData(
            runtime=self._data.runtime,
            state=ModelSelectionState.CONFIGURED,
            desired=desired,
            binding=binding,
            events=(*self._data.events, configured),
        )
        return self.data

    def report_effective(
        self,
        effective: RuntimeModelSelection,
        evidence: EvidenceLevel,
        evidence_source: str,
        correlation_id: str,
    ) -> ModelSelectionStateData:
        if self._data.state is not ModelSelectionState.CONFIGURED:
            raise InvalidModelSelection("model must be configured first")
        event = ModelSelectionEvent(
            name=ModelSelectionEventName.EFFECTIVE_REPORTED,
            correlation_id=correlation_id,
            effective=effective,
            evidence=evidence,
            evidence_source=evidence_source,
        )
        self._data = ModelSelectionStateData(
            runtime=self._data.runtime,
            state=self._data.state,
            desired=self._data.desired,
            binding=self._data.binding,
            effective=effective,
            effective_evidence=evidence,
            effective_evidence_source=evidence_source,
            events=(*self._data.events, event),
        )
        return self.data

    def clear(self, correlation_id: str) -> ModelSelectionStateData:
        if self._data.state not in {
            ModelSelectionState.CONFIGURED,
            ModelSelectionState.REJECTED,
        }:
            raise InvalidModelSelection(
                f"cannot clear model from {self._data.state.value}"
            )
        event = ModelSelectionEvent(
            name=ModelSelectionEventName.SELECTION_CLEARED,
            correlation_id=correlation_id,
        )
        self._data = ModelSelectionStateData(
            runtime=self._data.runtime,
            events=(*self._data.events, event),
        )
        return self.data

    def _validate_selection(
        self,
        desired: RuntimeModelSelection,
        catalog: RuntimeModelCatalog,
    ) -> RuntimeFailure | None:
        if catalog.runtime != self._data.runtime:
            return RuntimeFailure(
                code=RuntimeFailureCode.IDENTITY_MISMATCH,
                message="model catalog belongs to another runtime",
            )
        descriptor = catalog.find(desired.model)
        if descriptor is None:
            return RuntimeFailure(
                code=RuntimeFailureCode.MODEL_NOT_FOUND,
                message="requested model is not present in runtime catalog",
                details={"model": desired.model.model_dump(mode="json")},
            )
        if (
            desired.effort is not None
            and desired.effort not in descriptor.supported_efforts
        ):
            return RuntimeFailure(
                code=RuntimeFailureCode.EFFORT_UNSUPPORTED,
                message="requested effort is not supported by model",
                details={
                    "effort": desired.effort,
                    "supported_efforts": descriptor.supported_efforts,
                },
            )
        return None
