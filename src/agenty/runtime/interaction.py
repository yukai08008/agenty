"""Interaction policy guards and approval audit state for one runtime turn."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agenty.runtime.protocol import (
    INTERACTION_APPROVAL_CAPABILITY,
    INTERACTION_AUTO_APPROVE_CAPABILITY,
    ApprovalOutcome,
    CapabilityRecord,
    CapabilitySupport,
    EvidenceLevel,
    InteractionEvent,
    InteractionPolicyMode,
    RuntimeApprovalDecision,
    RuntimeApprovalRequest,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeInteractionPolicy,
)


class InteractionState(str, Enum):
    READY = "ready"
    WAITING_APPROVAL = "waiting_approval"
    CLOSED = "closed"


class InvalidInteraction(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        failure: RuntimeFailure | None = None,
    ) -> None:
        self.failure = failure
        super().__init__(message)


class InteractionStateData(BaseModel):
    """Serializable interaction state and audit trail for one turn."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    runtime: RuntimeIdentity
    turn_id: str
    correlation_id: str
    policy: RuntimeInteractionPolicy
    state: InteractionState = InteractionState.READY
    pending_request: RuntimeApprovalRequest | None = None
    audit_events: list[RuntimeEvent] = Field(default_factory=list)

    @field_validator("turn_id", "correlation_id")
    @classmethod
    def validate_context_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_state(self) -> "InteractionStateData":
        if (
            self.state is InteractionState.WAITING_APPROVAL
        ) != (self.pending_request is not None):
            raise ValueError("waiting approval state requires one pending request")
        for event in self.audit_events:
            if (
                event.runtime != self.runtime
                or event.turn_id != self.turn_id
                or event.correlation_id != self.correlation_id
                or not isinstance(event.name, InteractionEvent)
            ):
                raise ValueError("audit event belongs to another interaction")
        return self


class RuntimeInteractionMachine:
    def __init__(
        self,
        runtime: RuntimeIdentity,
        turn_id: str,
        correlation_id: str,
        policy: RuntimeInteractionPolicy,
        state_data: InteractionStateData | None = None,
    ) -> None:
        if state_data is not None and (
            state_data.runtime != runtime
            or state_data.turn_id != turn_id
            or state_data.correlation_id != correlation_id
            or state_data.policy != policy
        ):
            raise ValueError("state data belongs to another runtime or turn")
        self._data = state_data or InteractionStateData(
            runtime=runtime,
            turn_id=turn_id,
            correlation_id=correlation_id,
            policy=policy,
        )

    @property
    def data(self) -> InteractionStateData:
        return self._data

    @property
    def state(self) -> InteractionState:
        return self._data.state

    def prepare(
        self,
        capabilities: tuple[CapabilityRecord, ...],
    ) -> RuntimeEvent:
        if self.state is not InteractionState.READY or self._data.audit_events:
            raise InvalidInteraction("interaction policy is already prepared")
        required = self._required_capability()
        if required is not None and not self._supports(required, capabilities):
            failure = RuntimeFailure(
                code=RuntimeFailureCode.INTERACTION_UNSUPPORTED,
                message="runtime channel does not support interaction policy",
                details={
                    "policy": self._data.policy.mode.value,
                    "required_capability": required,
                },
            )
            raise InvalidInteraction(failure.message, failure=failure)
        return self._record(
            InteractionEvent.INTERACTION_POLICY_APPLIED,
            {
                "policy": self._data.policy.model_dump(mode="json"),
                "actor": "application",
            },
        )
    def request_approval(
        self,
        request: RuntimeApprovalRequest,
    ) -> RuntimeEvent:
        if self.state is not InteractionState.READY:
            raise InvalidInteraction("another approval request is already pending")
        if not self._data.audit_events:
            raise InvalidInteraction("interaction policy is not prepared")
        self._replace(
            pending_request=request,
            state=InteractionState.WAITING_APPROVAL,
        )
        event = self._record(
            InteractionEvent.APPROVAL_REQUESTED,
            {"request": request.model_dump(mode="json")},
        )
        return event

    def propose_decision(
        self,
        request_id: str,
        *,
        outcome: ApprovalOutcome | None = None,
        actor: str | None = None,
    ) -> RuntimeApprovalDecision:
        pending = self._pending(request_id)
        mode = self._data.policy.mode
        if mode is InteractionPolicyMode.ASK:
            if outcome is None or actor is None:
                raise InvalidInteraction("ask policy requires a human decision")
            return RuntimeApprovalDecision(
                request_id=pending.request_id,
                outcome=outcome,
                actor=actor,
                automatic=False,
            )
        approved = mode is InteractionPolicyMode.AUTO_APPROVE
        return RuntimeApprovalDecision(
            request_id=pending.request_id,
            outcome=(
                ApprovalOutcome.APPROVED
                if approved
                else ApprovalOutcome.REJECTED
            ),
            actor=f"policy:{mode.value}",
            automatic=True,
        )

    def commit_decision(
        self,
        decision: RuntimeApprovalDecision,
    ) -> RuntimeEvent:
        pending = self._pending(decision.request_id)
        event = self._record(
            InteractionEvent.APPROVAL_DECIDED,
            {
                "request": pending.model_dump(mode="json"),
                "decision": decision.model_dump(mode="json"),
            },
        )
        self._replace(
            pending_request=None,
            state=InteractionState.READY,
        )
        return event

    def cancel_requested(self, actor: str) -> RuntimeEvent:
        actor = actor.strip()
        if not actor:
            raise InvalidInteraction("cancel actor must not be empty")
        if self.state is InteractionState.CLOSED:
            raise InvalidInteraction("interaction is closed")
        return self._record(
            InteractionEvent.TURN_CANCEL_REQUESTED,
            {"actor": actor},
        )

    def close(self) -> None:
        self._replace(
            pending_request=None,
            state=InteractionState.CLOSED,
        )

    def snapshot(self) -> InteractionStateData:
        return self._data.model_copy(deep=True)

    def _required_capability(self) -> str | None:
        if self._data.policy.mode is InteractionPolicyMode.ASK:
            return INTERACTION_APPROVAL_CAPABILITY
        if self._data.policy.mode is InteractionPolicyMode.AUTO_APPROVE:
            return INTERACTION_AUTO_APPROVE_CAPABILITY
        return None

    def _supports(
        self,
        capability: str,
        records: tuple[CapabilityRecord, ...],
    ) -> bool:
        return any(
            record.runtime == self._data.runtime
            and record.capability == capability
            and record.support is CapabilitySupport.SUPPORTED
            and record.evidence
            in {
                EvidenceLevel.INTEGRATION_VERIFIED,
                EvidenceLevel.LIVE_VERIFIED,
            }
            for record in records
        )

    def _pending(self, request_id: str) -> RuntimeApprovalRequest:
        pending = self._data.pending_request
        if pending is None or pending.request_id != request_id:
            raise InvalidInteraction("approval request ID does not match pending request")
        return pending

    def _record(
        self,
        name: InteractionEvent,
        payload: dict,
    ) -> RuntimeEvent:
        event = RuntimeEvent(
            name=name,
            runtime=self._data.runtime,
            correlation_id=self._data.correlation_id,
            turn_id=self._data.turn_id,
            payload=payload,
        )
        self._replace(audit_events=[*self._data.audit_events, event])
        return event

    def _replace(self, **updates: object) -> None:
        values = self._data.model_dump()
        values.update(updates)
        self._data = InteractionStateData.model_validate(values)
