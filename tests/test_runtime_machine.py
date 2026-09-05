import pytest

from agenty.runtime.adapters import RuntimeAdapterError
from agenty.runtime.machine import InvalidRuntimeTransition, RuntimeMachine
from agenty.runtime.models import (
    RuntimeCapability,
    RuntimeEventType,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeInfo,
    RuntimeState,
)


class AvailableAdapter:
    runtime_id = "fake"

    def probe(self):
        return RuntimeInfo(
            runtime_id="fake",
            kind="fake",
            version="1.0.0",
            executable="/fake",
            capabilities=frozenset({RuntimeCapability.SESSIONS}),
        )


class MissingAdapter:
    runtime_id = "missing"

    def probe(self):
        raise RuntimeAdapterError(
            RuntimeFailure(
                code=RuntimeFailureCode.NOT_FOUND,
                message="missing",
            )
        )


def test_successful_probe_drives_runtime_to_ready():
    machine = RuntimeMachine(AvailableAdapter())

    snapshot = machine.probe()

    assert snapshot.state == RuntimeState.READY
    assert [event.type for event in snapshot.events] == [
        RuntimeEventType.PROBE_REQUESTED,
        RuntimeEventType.PROBE_SUCCEEDED,
    ]
    assert snapshot.info is not None


def test_failed_probe_drives_runtime_to_unavailable():
    snapshot = RuntimeMachine(MissingAdapter()).probe()

    assert snapshot.state == RuntimeState.UNAVAILABLE
    assert snapshot.failure is not None
    assert snapshot.failure.code == RuntimeFailureCode.NOT_FOUND


def test_invalid_event_keeps_state_unchanged():
    machine = RuntimeMachine(AvailableAdapter())

    with pytest.raises(InvalidRuntimeTransition):
        machine.send(RuntimeEventType.PROBE_SUCCEEDED)

    assert machine.state == RuntimeState.UNKNOWN
    assert machine.snapshot().events == ()
