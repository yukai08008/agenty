"""Generic orchestration for a side-effect-free runtime probe."""

from __future__ import annotations

from uuid import uuid4

from agenty.runtime.adapters import RuntimeAdapter, RuntimeAdapterError
from agenty.runtime.availability import AvailabilityMachine
from agenty.runtime.protocol import (
    AvailabilityEvent,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeSnapshot,
)


class RuntimeProbeMachine:
    """Drive AvailabilityMachine while an adapter gathers observations."""

    def __init__(self, adapter: RuntimeAdapter) -> None:
        self.adapter = adapter
        self.availability = AvailabilityMachine(adapter.identity)

    def probe(self, correlation_id: str | None = None) -> RuntimeSnapshot:
        correlation_id = correlation_id or str(uuid4())
        self._apply(
            AvailabilityEvent.PROBE_STARTED,
            self.adapter.identity,
            correlation_id,
        )

        try:
            runtime = self.adapter.detect()
        except RuntimeAdapterError as exc:
            self._apply(exc.event, self.adapter.identity, correlation_id, exc.failure)
            return self.snapshot()
        except Exception as exc:
            self._apply(
                AvailabilityEvent.RUNTIME_UNAVAILABLE,
                self.adapter.identity,
                correlation_id,
                RuntimeFailure(
                    code=RuntimeFailureCode.INTERNAL,
                    message="runtime detection raised an unexpected error",
                    details={"error_type": type(exc).__name__, "error": str(exc)},
                ),
            )
            return self.snapshot()

        self._apply(AvailabilityEvent.RUNTIME_DETECTED, runtime, correlation_id)

        try:
            capabilities = self.adapter.probe_capabilities(runtime)
        except RuntimeAdapterError as exc:
            self._apply(
                AvailabilityEvent.CAPABILITY_PROBE_FAILED,
                runtime,
                correlation_id,
                exc.failure,
            )
        except Exception as exc:
            self._apply(
                AvailabilityEvent.CAPABILITY_PROBE_FAILED,
                runtime,
                correlation_id,
                RuntimeFailure(
                    code=RuntimeFailureCode.INTERNAL,
                    message="capability probe raised an unexpected error",
                    details={"error_type": type(exc).__name__, "error": str(exc)},
                ),
            )
        else:
            self.availability.apply(
                RuntimeEvent(
                    name=AvailabilityEvent.CAPABILITIES_RESOLVED,
                    runtime=runtime,
                    correlation_id=correlation_id,
                    payload={"capabilities": capabilities},
                )
            )
        return self.snapshot()

    def snapshot(self) -> RuntimeSnapshot:
        return self.availability.snapshot()

    def _apply(
        self,
        name: AvailabilityEvent,
        runtime: RuntimeIdentity,
        correlation_id: str,
        failure: RuntimeFailure | None = None,
    ) -> None:
        payload = {"failure": failure} if failure is not None else {}
        self.availability.apply(
            RuntimeEvent(
                name=name,
                runtime=runtime,
                correlation_id=correlation_id,
                payload=payload,
            )
        )
