from agenty.runtime.adapters import RuntimeAdapterError
from agenty.runtime.machine import RuntimeProbeMachine
from agenty.runtime.protocol import (
    AvailabilityEvent,
    AvailabilityState,
    CapabilityRecord,
    CapabilitySupport,
    ChannelMode,
    EvidenceLevel,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
)


class AvailableAdapter:
    @property
    def identity(self):
        return RuntimeIdentity(
            runtime_id="fake",
            runtime_kind="fake",
            channel=ChannelMode.TRANSIENT_PROCESS,
        )

    def detect(self):
        return self.identity.model_copy(
            update={"runtime_version": "1.0.0", "executable": "/fake"}
        )

    def probe_capabilities(self, runtime):
        return (
            CapabilityRecord(
                capability="session.create",
                runtime=runtime,
                support=CapabilitySupport.SUPPORTED,
                evidence=EvidenceLevel.PROBE_VERIFIED,
                evidence_source="fake probe",
            ),
        )


class MissingAdapter(AvailableAdapter):
    def detect(self):
        raise RuntimeAdapterError(
            AvailabilityEvent.RUNTIME_MISSING,
            RuntimeFailure(
                code=RuntimeFailureCode.NOT_FOUND,
                message="missing",
            ),
        )


def test_successful_probe_drives_availability_to_available():
    machine = RuntimeProbeMachine(AvailableAdapter())

    snapshot = machine.probe(correlation_id="probe-1")

    assert snapshot.availability is AvailabilityState.AVAILABLE
    assert snapshot.runtime.runtime_version == "1.0.0"
    assert snapshot.capabilities[0].capability == "session.create"
    assert [event.name for event in machine.availability.events] == [
        AvailabilityEvent.PROBE_STARTED,
        AvailabilityEvent.RUNTIME_DETECTED,
        AvailabilityEvent.CAPABILITIES_RESOLVED,
    ]
    assert {
        event.correlation_id for event in machine.availability.events
    } == {"probe-1"}


def test_failed_detection_drives_availability_to_unavailable():
    snapshot = RuntimeProbeMachine(MissingAdapter()).probe()

    assert snapshot.availability is AvailabilityState.UNAVAILABLE
    assert snapshot.failure is not None
    assert snapshot.failure.code is RuntimeFailureCode.NOT_FOUND
