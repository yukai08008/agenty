"""Generic orchestration for one runtime turn."""

from __future__ import annotations

import time
from threading import Condition, RLock

from agenty.runtime.adapters import (
    RuntimeTurnAdapter,
    RuntimeTurnAdapterError,
    RuntimeTurnControl,
)
from agenty.runtime.events import (
    InvalidRuntimeEventStream,
    RuntimeEventStreamMachine,
    RuntimeEventStreamStateData,
)
from agenty.runtime.interaction import (
    InteractionStateData,
    InvalidInteraction,
    RuntimeInteractionMachine,
)
from agenty.runtime.protocol import (
    ApprovalOutcome,
    CapabilityRecord,
    InteractionPolicyMode,
    RuntimeApprovalDecision,
    RuntimeApprovalRequest,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeTurnRequest,
    TurnEvent,
    TurnState,
)
from agenty.runtime.turn import (
    InvalidTurnTransition,
    TurnMachine,
    TurnStateData,
)

_TERMINAL_STATES = {
    TurnState.SUCCEEDED,
    TurnState.FAILED,
    TurnState.CANCELLED,
    TurnState.TIMED_OUT,
}


class RuntimeTurnRunner:
    """Apply adapter events to a validated TurnMachine."""

    def __init__(
        self,
        adapter: RuntimeTurnAdapter,
        runtime: RuntimeIdentity,
        capabilities: tuple[CapabilityRecord, ...] = (),
        approval_timeout_seconds: float = 300,
    ) -> None:
        self.adapter = adapter
        self.runtime = runtime
        self.capabilities = capabilities
        if approval_timeout_seconds <= 0:
            raise ValueError("approval_timeout_seconds must be positive")
        self.approval_timeout_seconds = approval_timeout_seconds
        self._last_event_stream: RuntimeEventStreamStateData | None = None
        self._last_interaction: InteractionStateData | None = None
        self._machine: TurnMachine | None = None
        self._stream: RuntimeEventStreamMachine | None = None
        self._interaction: RuntimeInteractionMachine | None = None
        self._control: RuntimeTurnControl | None = None
        self._lock = RLock()
        self._approval_changed = Condition(self._lock)

    @property
    def last_event_stream(self) -> RuntimeEventStreamStateData | None:
        if self._last_event_stream is None:
            return None
        return self._last_event_stream.model_copy(deep=True)

    @property
    def last_interaction(self) -> InteractionStateData | None:
        if self._last_interaction is None:
            return None
        return self._last_interaction.model_copy(deep=True)

    @property
    def active_interaction(self) -> InteractionStateData | None:
        with self._lock:
            if self._interaction is None:
                return None
            return self._interaction.snapshot()

    def run(self, request: RuntimeTurnRequest) -> TurnStateData:
        with self._lock:
            if self._machine is not None:
                raise RuntimeError("runner already has an active turn")
            machine = TurnMachine(self.runtime, request)
            stream = RuntimeEventStreamMachine(
                self.runtime,
                request.correlation_id,
                turn_id=request.turn_id,
            )
            interaction = RuntimeInteractionMachine(
                self.runtime,
                request.turn_id,
                request.correlation_id,
                request.interaction,
            )
            control = RuntimeTurnControl()
            stream.start()
            self._apply(
                machine,
                stream,
                self._event(TurnEvent.TURN_CREATED, request),
            )
            self._apply(
                machine,
                stream,
                self._event(TurnEvent.TURN_SUBMISSION_STARTED, request),
            )
            self._last_event_stream = None
            self._last_interaction = None
            self._machine = machine
            self._stream = stream
            self._interaction = interaction
            self._control = control

        try:
            policy_event = interaction.prepare(self.capabilities)
            self._apply(
                machine,
                stream,
                policy_event,
            )
            for event in self.adapter.iter_turn_events(
                self.runtime,
                request,
                control,
            ):
                self._apply(machine, stream, event)
                if event.name is TurnEvent.TURN_WAITING_FOR_APPROVAL:
                    try:
                        approval = RuntimeApprovalRequest.model_validate(
                            event.payload.get("request")
                        )
                    except ValueError as exc:
                        raise InvalidTurnTransition(
                            "approval event requires a RuntimeApprovalRequest payload"
                        ) from exc
                    audit_event = interaction.request_approval(approval)
                    self._apply(machine, stream, audit_event)
                    if request.interaction.mode is not InteractionPolicyMode.ASK:
                        decision = interaction.propose_decision(
                            approval.request_id
                        )
                        self.adapter.reply_approval(decision)
                        self._apply(
                            machine,
                            stream,
                            interaction.commit_decision(decision),
                        )
                    else:
                        deadline = (
                            time.monotonic() + self.approval_timeout_seconds
                        )
                        with self._approval_changed:
                            while (
                                interaction.data.pending_request is not None
                                and not control.cancelled
                            ):
                                remaining = deadline - time.monotonic()
                                if remaining <= 0:
                                    control.cancel("approval_timeout")
                                    raise RuntimeTurnAdapterError(
                                        RuntimeFailure(
                                            code=RuntimeFailureCode.TURN_TIMEOUT,
                                            message="runtime approval timed out",
                                            details={
                                                "request_id": approval.request_id,
                                                "timeout_seconds": (
                                                    self.approval_timeout_seconds
                                                ),
                                            },
                                        ),
                                        timed_out=True,
                                    )
                                self._approval_changed.wait(remaining)
                        if control.cancelled:
                            raise RuntimeTurnAdapterError(
                                RuntimeFailure(
                                    code=RuntimeFailureCode.TURN_FAILED,
                                    message="runtime turn was cancelled",
                                    details={"actor": control.actor},
                                ),
                                cancelled=True,
                            )
        except RuntimeTurnAdapterError as exc:
            if exc.cancelled:
                self._apply(
                    machine,
                    stream,
                    self._event(
                        TurnEvent.TURN_CANCELLED,
                        request,
                        session_id=machine.data.session_id,
                    ),
                )
            else:
                self._fail(
                    machine,
                    stream,
                    request,
                    exc.failure,
                    exc.timed_out,
                )
        except InvalidInteraction as exc:
            failure = exc.failure or RuntimeFailure(
                code=RuntimeFailureCode.INVALID_OUTPUT,
                message="runtime interaction was invalid",
                details={"error": str(exc)},
            )
            self._fail(machine, stream, request, failure, False)
        except InvalidRuntimeEventStream as exc:
            self._fail(
                machine,
                stream,
                request,
                RuntimeFailure(
                    code=RuntimeFailureCode.INVALID_OUTPUT,
                    message="runtime adapter emitted an invalid event stream",
                    details={"error": str(exc)},
                ),
                False,
            )
        except InvalidTurnTransition as exc:
            self._fail(
                machine,
                stream,
                request,
                RuntimeFailure(
                    code=RuntimeFailureCode.INVALID_OUTPUT,
                    message="runtime adapter emitted an invalid turn event",
                    details={"error": str(exc)},
                ),
                False,
            )
        except Exception as exc:
            self._fail(
                machine,
                stream,
                request,
                RuntimeFailure(
                    code=RuntimeFailureCode.INTERNAL,
                    message="runtime turn adapter raised an unexpected error",
                    details={
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                ),
                False,
            )

        if machine.state not in _TERMINAL_STATES:
            self._fail(
                machine,
                stream,
                request,
                RuntimeFailure(
                    code=RuntimeFailureCode.INVALID_OUTPUT,
                    message="runtime turn ended without a terminal event",
                ),
                False,
            )
        stream.close()
        interaction.close()
        with self._lock:
            self._last_event_stream = stream.snapshot()
            self._last_interaction = interaction.snapshot()
            if self._machine is machine:
                self._machine = None
                self._stream = None
                self._interaction = None
                self._control = None
        return machine.snapshot()

    def reply_approval(
        self,
        request_id: str,
        outcome: ApprovalOutcome,
        actor: str,
    ) -> RuntimeApprovalDecision:
        with self._lock:
            machine, stream, interaction = self._active_turn()
            decision = interaction.propose_decision(
                request_id,
                outcome=outcome,
                actor=actor,
            )
            try:
                self.adapter.reply_approval(decision)
            except RuntimeTurnAdapterError:
                control = self._control
                assert control is not None
                control.cancel("approval_delivery_failed")
                self._approval_changed.notify_all()
                raise
            self._apply(
                machine,
                stream,
                interaction.commit_decision(decision),
            )
            self._approval_changed.notify_all()
            return decision

    def cancel(self, actor: str = "application") -> None:
        with self._lock:
            machine, stream, interaction = self._active_turn()
            control = self._control
            assert control is not None
            event = interaction.cancel_requested(actor)
            self._apply(machine, stream, event)
            control.cancel(actor)
            self._approval_changed.notify_all()

    def _fail(
        self,
        machine: TurnMachine,
        stream: RuntimeEventStreamMachine,
        request: RuntimeTurnRequest,
        failure: RuntimeFailure,
        timed_out: bool,
    ) -> None:
        name = (
            TurnEvent.TURN_TIMED_OUT
            if timed_out and machine.state is not TurnState.SUBMITTING
            else TurnEvent.TURN_FAILED
        )
        self._apply(
            machine,
            stream,
            self._event(
                name,
                request,
                session_id=machine.data.session_id,
                payload={"failure": failure},
            ),
        )

    def _apply(
        self,
        machine: TurnMachine,
        stream: RuntimeEventStreamMachine,
        event: RuntimeEvent,
    ) -> None:
        with self._lock:
            preview = RuntimeEventStreamMachine(
                stream.data.runtime,
                stream.data.correlation_id,
                turn_id=stream.data.turn_id,
                state_data=stream.snapshot(),
            ).append(event)
            machine.validate(preview)
            machine.apply(stream.append(event))

    def _active_turn(
        self,
    ) -> tuple[
        TurnMachine,
        RuntimeEventStreamMachine,
        RuntimeInteractionMachine,
    ]:
        if (
            self._machine is None
            or self._stream is None
            or self._interaction is None
        ):
            raise RuntimeError("no turn is currently running")
        return self._machine, self._stream, self._interaction

    def _event(
        self,
        name: TurnEvent,
        request: RuntimeTurnRequest,
        *,
        session_id: str | None = None,
        payload: dict | None = None,
    ) -> RuntimeEvent:
        return RuntimeEvent(
            name=name,
            runtime=self.runtime,
            correlation_id=request.correlation_id,
            turn_id=request.turn_id,
            session_id=session_id,
            payload=payload or {},
        )
