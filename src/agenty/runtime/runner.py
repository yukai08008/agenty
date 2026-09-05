"""Generic orchestration for one runtime turn."""

from __future__ import annotations

from agenty.runtime.adapters import RuntimeTurnAdapter, RuntimeTurnAdapterError
from agenty.runtime.protocol import (
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeTurnRequest,
    TurnEvent,
    TurnState,
)
from agenty.runtime.turn import TurnMachine, TurnStateData


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
    ) -> None:
        self.adapter = adapter
        self.runtime = runtime

    def run(self, request: RuntimeTurnRequest) -> TurnStateData:
        machine = TurnMachine(self.runtime, request)
        machine.apply(self._event(TurnEvent.TURN_CREATED, request))
        machine.apply(self._event(TurnEvent.TURN_SUBMISSION_STARTED, request))

        try:
            for event in self.adapter.iter_turn_events(self.runtime, request):
                machine.apply(event)
        except RuntimeTurnAdapterError as exc:
            self._fail(machine, request, exc.failure, exc.timed_out)
        except Exception as exc:
            self._fail(
                machine,
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
                request,
                RuntimeFailure(
                    code=RuntimeFailureCode.INVALID_OUTPUT,
                    message="runtime turn ended without a terminal event",
                ),
                False,
            )
        return machine.snapshot()

    def _fail(
        self,
        machine: TurnMachine,
        request: RuntimeTurnRequest,
        failure: RuntimeFailure,
        timed_out: bool,
    ) -> None:
        name = (
            TurnEvent.TURN_TIMED_OUT
            if timed_out and machine.state is not TurnState.SUBMITTING
            else TurnEvent.TURN_FAILED
        )
        machine.apply(
            self._event(
                name,
                request,
                session_id=machine.data.session_id,
                payload={"failure": failure},
            )
        )

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
