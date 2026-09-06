"""Generic orchestration for one runtime turn."""

from __future__ import annotations

from agenty.runtime.adapters import RuntimeTurnAdapter, RuntimeTurnAdapterError
from agenty.runtime.events import (
    InvalidRuntimeEventStream,
    RuntimeEventStreamMachine,
    RuntimeEventStreamStateData,
)
from agenty.runtime.protocol import (
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
    ) -> None:
        self.adapter = adapter
        self.runtime = runtime
        self._last_event_stream: RuntimeEventStreamStateData | None = None

    @property
    def last_event_stream(self) -> RuntimeEventStreamStateData | None:
        if self._last_event_stream is None:
            return None
        return self._last_event_stream.model_copy(deep=True)

    def run(self, request: RuntimeTurnRequest) -> TurnStateData:
        self._last_event_stream = None
        machine = TurnMachine(self.runtime, request)
        stream = RuntimeEventStreamMachine(
            self.runtime,
            request.correlation_id,
            turn_id=request.turn_id,
        )
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

        try:
            for event in self.adapter.iter_turn_events(self.runtime, request):
                self._apply(machine, stream, event)
        except RuntimeTurnAdapterError as exc:
            self._fail(
                machine,
                stream,
                request,
                exc.failure,
                exc.timed_out,
            )
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
        self._last_event_stream = stream.snapshot()
        return machine.snapshot()

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
        machine.apply(stream.append(event))

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
