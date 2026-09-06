import pytest
from pydantic import ValidationError

from agenty.runtime.adapters import RuntimeAdapterError
from agenty.runtime.protocol import (
    AvailabilityEvent,
    AvailabilityState,
    ChannelMode,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeTarget,
)
from agenty.runtime.selection import (
    InvalidRuntimeSelection,
    RuntimeAdapterRegistry,
    RuntimeSelectionEventName,
    RuntimeSelectionMachine,
    RuntimeSelectionState,
    RuntimeSelectionStateData,
)


class FakeAdapter:
    def __init__(
        self,
        *,
        actual_kind: str = "fake",
        actual_version: str = "1.2.3",
        failure: RuntimeFailure | None = None,
    ) -> None:
        self.actual_kind = actual_kind
        self.actual_version = actual_version
        self.failure = failure
        self.detect_calls = 0

    @property
    def identity(self):
        return RuntimeIdentity(
            runtime_id="local-fake",
            runtime_kind=self.actual_kind,
            channel=ChannelMode.TRANSIENT_PROCESS,
        )

    def detect(self):
        self.detect_calls += 1
        if self.failure is not None:
            raise RuntimeAdapterError(
                AvailabilityEvent.RUNTIME_MISSING,
                self.failure,
            )
        return self.identity.model_copy(
            update={"runtime_version": self.actual_version}
        )

    def probe_capabilities(self, runtime):
        return ()


def target(version: str = "1.2.3") -> RuntimeTarget:
    return RuntimeTarget(runtime_kind="fake", runtime_version=version)


@pytest.mark.parametrize(
    "values",
    [
        {"runtime_kind": "", "runtime_version": "1.2.3"},
        {"runtime_kind": "fake", "runtime_version": " "},
        {"runtime_kind": "fake", "runtime_version": ">=1.2.3"},
    ],
)
def test_runtime_target_requires_kind_and_exact_version(values):
    with pytest.raises(ValidationError, match="must not be empty|exact version"):
        RuntimeTarget(**values)


def test_exact_registered_target_is_selected_after_probe():
    adapter = FakeAdapter()
    registry = RuntimeAdapterRegistry()
    registry.register(target(), lambda: adapter)
    machine = RuntimeSelectionMachine(registry)

    result = machine.select(target(), "selection-1")

    assert result.state is RuntimeSelectionState.SELECTED
    assert result.snapshot is not None
    assert result.snapshot.availability is AvailabilityState.AVAILABLE
    assert result.snapshot.runtime.runtime_version == "1.2.3"
    assert adapter.detect_calls == 1
    assert [event.name for event in result.events] == [
        RuntimeSelectionEventName.SELECTION_STARTED,
        RuntimeSelectionEventName.RUNTIME_SELECTED,
    ]


def test_unregistered_runtime_kind_is_rejected_without_starting_adapter():
    registry = RuntimeAdapterRegistry()
    machine = RuntimeSelectionMachine(registry)

    result = machine.select(target(), "selection-1")

    assert result.state is RuntimeSelectionState.REJECTED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.ADAPTER_NOT_REGISTERED
    assert result.failure.details["registered_versions"] == ()


def test_unregistered_version_does_not_fall_back_to_another_adapter():
    adapter = FakeAdapter()
    registry = RuntimeAdapterRegistry()
    registry.register(target("1.2.3"), lambda: adapter)
    machine = RuntimeSelectionMachine(registry)

    result = machine.select(target("1.2.4"), "selection-1")

    assert result.state is RuntimeSelectionState.REJECTED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.ADAPTER_NOT_REGISTERED
    assert result.failure.details["registered_versions"] == ("1.2.3",)
    assert adapter.detect_calls == 0


@pytest.mark.parametrize(
    ("actual_kind", "actual_version"),
    [("other", "1.2.3"), ("fake", "1.2.4")],
)
def test_detected_identity_mismatch_is_rejected(actual_kind, actual_version):
    adapter = FakeAdapter(
        actual_kind=actual_kind,
        actual_version=actual_version,
    )
    registry = RuntimeAdapterRegistry()
    registry.register(
        target(),
        lambda: adapter,
    )
    machine = RuntimeSelectionMachine(registry)

    result = machine.select(target(), "selection-1")

    assert result.state is RuntimeSelectionState.REJECTED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.IDENTITY_MISMATCH
    assert adapter.detect_calls == (0 if actual_kind == "other" else 1)


def test_adapter_factory_failure_rejects_without_stranding_resolving_state():
    def broken_factory():
        raise RuntimeError("factory failed")

    registry = RuntimeAdapterRegistry()
    registry.register(target(), broken_factory)
    machine = RuntimeSelectionMachine(registry)

    result = machine.select(target(), "selection-1")

    assert result.state is RuntimeSelectionState.REJECTED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.INTERNAL
    assert result.failure.details["error_type"] == "RuntimeError"


def test_probe_failure_is_preserved_in_rejected_selection():
    failure = RuntimeFailure(
        code=RuntimeFailureCode.NOT_FOUND,
        message="runtime executable not found",
    )
    registry = RuntimeAdapterRegistry()
    registry.register(target(), lambda: FakeAdapter(failure=failure))
    machine = RuntimeSelectionMachine(registry)

    result = machine.select(target(), "selection-1")

    assert result.state is RuntimeSelectionState.REJECTED
    assert result.failure == failure
    assert result.snapshot is not None
    assert result.snapshot.availability is AvailabilityState.UNAVAILABLE


def test_selected_runtime_must_be_cleared_before_reselection():
    registry = RuntimeAdapterRegistry()
    registry.register(target(), FakeAdapter)
    machine = RuntimeSelectionMachine(registry)
    machine.select(target(), "selection-1")
    before = machine.snapshot()

    with pytest.raises(InvalidRuntimeSelection, match="cannot select"):
        machine.select(target(), "selection-2")

    assert machine.snapshot() == before
    cleared = machine.clear("clear-1")
    assert cleared.state is RuntimeSelectionState.UNSELECTED
    assert cleared.target is None


def test_rejected_state_round_trips_and_can_retry():
    empty_registry = RuntimeAdapterRegistry()
    machine = RuntimeSelectionMachine(empty_registry)
    machine.select(target(), "selection-1")
    restored_data = RuntimeSelectionStateData.model_validate_json(
        machine.data.model_dump_json()
    )

    registry = RuntimeAdapterRegistry()
    registry.register(target(), FakeAdapter)
    restored = RuntimeSelectionMachine(registry, restored_data)
    result = restored.select(target(), "selection-2")

    assert result.state is RuntimeSelectionState.SELECTED
    assert len(result.events) == 4


def test_selection_state_data_rejects_inconsistent_selected_state():
    with pytest.raises(ValidationError, match="requires target and snapshot"):
        RuntimeSelectionStateData(state=RuntimeSelectionState.SELECTED)


def test_duplicate_exact_registration_is_rejected():
    registry = RuntimeAdapterRegistry()
    registry.register(target(), FakeAdapter)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(target(), FakeAdapter)
