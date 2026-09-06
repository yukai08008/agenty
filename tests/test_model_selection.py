import pytest
from pydantic import ValidationError

from agenty.runtime import (
    ChannelMode,
    EvidenceLevel,
    InvalidModelSelection,
    ModelSelectionEventName,
    ModelSelectionState,
    ModelSelectionStateData,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeModelBinding,
    RuntimeModelCatalog,
    RuntimeModelDescriptor,
    RuntimeModelRef,
    RuntimeModelSelection,
    RuntimeModelSelectionMachine,
)


def runtime(runtime_id: str = "local-opencode") -> RuntimeIdentity:
    return RuntimeIdentity(
        runtime_id=runtime_id,
        runtime_kind="opencode",
        runtime_version="1.18.26",
        executable="/opt/homebrew/bin/opencode",
        channel=ChannelMode.TRANSIENT_PROCESS,
    )


def model_ref(model_id: str = "reasoner") -> RuntimeModelRef:
    return RuntimeModelRef(
        model_type="language",
        provider_id="provider",
        model_id=model_id,
    )


def descriptor(
    identity: RuntimeIdentity,
    model_id: str = "reasoner",
) -> RuntimeModelDescriptor:
    return RuntimeModelDescriptor(
        runtime=identity,
        model=model_ref(model_id),
        display_name="Reasoner",
        supported_efforts=("low", "high"),
        evidence=EvidenceLevel.PROBE_VERIFIED,
        evidence_source="fake models --verbose",
    )


def catalog(identity: RuntimeIdentity) -> RuntimeModelCatalog:
    return RuntimeModelCatalog(
        runtime=identity,
        models=(descriptor(identity), descriptor(identity, "other")),
    )


def selection(
    model_id: str = "reasoner",
    effort: str | None = "high",
) -> RuntimeModelSelection:
    return RuntimeModelSelection(model=model_ref(model_id), effort=effort)


def test_model_identity_keeps_type_provider_and_id_separate():
    model = model_ref()

    assert model.model_type == "language"
    assert model.provider_id == "provider"
    assert model.model_id == "reasoner"
    assert model.qualified_id == "provider/reasoner"


def test_valid_model_and_effort_produce_runtime_bound_configuration():
    identity = runtime()
    machine = RuntimeModelSelectionMachine(identity)

    result = machine.configure(selection(), catalog(identity), "select-1")

    assert result.state is ModelSelectionState.CONFIGURED
    assert result.desired == selection()
    assert result.effective is None
    assert result.binding is not None
    assert result.binding.runtime == identity
    assert result.binding.selection == selection()
    assert [event.name for event in result.events] == [
        ModelSelectionEventName.SELECTION_REQUESTED,
        ModelSelectionEventName.SELECTION_CONFIGURED,
    ]


def test_missing_model_is_rejected_before_execution():
    identity = runtime()

    result = RuntimeModelSelectionMachine(identity).configure(
        selection("missing"),
        catalog(identity),
        "select-1",
    )

    assert result.state is ModelSelectionState.REJECTED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.MODEL_NOT_FOUND
    assert result.binding is None


def test_unsupported_effort_is_rejected_before_execution():
    identity = runtime()

    result = RuntimeModelSelectionMachine(identity).configure(
        selection(effort="max"),
        catalog(identity),
        "select-1",
    )

    assert result.state is ModelSelectionState.REJECTED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.EFFORT_UNSUPPORTED
    assert result.failure.details["supported_efforts"] == ("low", "high")


def test_catalog_from_another_runtime_is_rejected():
    identity = runtime()

    result = RuntimeModelSelectionMachine(identity).configure(
        selection(),
        catalog(runtime("other-opencode")),
        "select-1",
    )

    assert result.state is ModelSelectionState.REJECTED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.IDENTITY_MISMATCH


def test_effective_selection_does_not_overwrite_desired_selection():
    identity = runtime()
    machine = RuntimeModelSelectionMachine(identity)
    machine.configure(selection(), catalog(identity), "select-1")
    actual = selection("other", effort="low")

    result = machine.report_effective(
        actual,
        EvidenceLevel.INTEGRATION_VERIFIED,
        "runtime response model metadata",
        "turn-1",
    )

    assert result.desired == selection()
    assert result.effective == actual
    assert result.effective_evidence is EvidenceLevel.INTEGRATION_VERIFIED


def test_state_round_trip_retains_desired_effective_and_evidence():
    identity = runtime()
    machine = RuntimeModelSelectionMachine(identity)
    machine.configure(selection(), catalog(identity), "select-1")
    machine.report_effective(
        selection("other", "low"),
        EvidenceLevel.INTEGRATION_VERIFIED,
        "runtime response model metadata",
        "turn-1",
    )

    restored_data = ModelSelectionStateData.model_validate_json(
        machine.data.model_dump_json()
    )
    restored = RuntimeModelSelectionMachine(identity, restored_data)

    assert restored.data == machine.data


def test_advertised_capability_cannot_be_reported_as_effective():
    identity = runtime()
    machine = RuntimeModelSelectionMachine(identity)
    machine.configure(selection(), catalog(identity), "select-1")
    before = machine.data

    with pytest.raises(ValidationError, match="execution-level"):
        machine.report_effective(
            selection(),
            EvidenceLevel.ADVERTISED,
            "run --help",
            "turn-1",
        )

    assert machine.data == before


def test_rejected_selection_can_be_cleared_and_reconfigured():
    identity = runtime()
    machine = RuntimeModelSelectionMachine(identity)
    machine.configure(selection("missing"), catalog(identity), "select-1")

    machine.clear("clear-1")
    result = machine.configure(selection(), catalog(identity), "select-2")

    assert result.state is ModelSelectionState.CONFIGURED
    assert len(result.events) == 5


def test_configured_selection_must_be_cleared_before_change():
    identity = runtime()
    machine = RuntimeModelSelectionMachine(identity)
    machine.configure(selection(), catalog(identity), "select-1")
    before = machine.data

    with pytest.raises(InvalidModelSelection):
        machine.configure(selection("other"), catalog(identity), "select-2")

    assert machine.data == before


def test_binding_rejects_effort_not_supported_by_descriptor():
    identity = runtime()
    with pytest.raises(ValidationError, match="not supported"):
        RuntimeModelBinding(
            runtime=identity,
            selection=selection(effort="max"),
            descriptor=descriptor(identity),
        )


def test_persisted_state_rejects_inconsistent_configured_shape():
    with pytest.raises(ValidationError, match="configured state"):
        ModelSelectionStateData(
            runtime=runtime(),
            state=ModelSelectionState.CONFIGURED,
            desired=selection(),
        )
