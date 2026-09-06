from pathlib import Path

import pytest
from pydantic import ValidationError

from agenty.runtime import (
    ChannelMode,
    InvalidSessionTransition,
    ProjectEnvironment,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeSessionBinding,
    RuntimeSessionBindingCatalog,
    RuntimeSessionCoordinator,
    RuntimeSessionRequest,
    RuntimeTurnRequest,
    SessionBindingCatalogState,
    SessionEvent,
    SessionMachine,
    SessionOpenMode,
    SessionState,
    SessionStateData,
)


def runtime(runtime_id: str = "local-opencode") -> RuntimeIdentity:
    return RuntimeIdentity(
        runtime_id=runtime_id,
        runtime_kind="opencode",
        runtime_version="1.18.26",
        executable="/usr/local/bin/opencode",
        channel=ChannelMode.TRANSIENT_PROCESS,
    )


def environment(
    root: Path, environment_id: str = "env-main"
) -> ProjectEnvironment:
    return ProjectEnvironment(
        environment_id=environment_id,
        project_id="agenty",
        working_directory=str(root),
        revision="abc123",
    )


def request(
    env: ProjectEnvironment,
    mode: SessionOpenMode = SessionOpenMode.NEW,
    session_id: str | None = None,
) -> RuntimeSessionRequest:
    return RuntimeSessionRequest(
        mode=mode,
        correlation_id="request-1",
        environment=env,
        session_id=session_id,
    )


def session_event(machine: SessionMachine, name: SessionEvent) -> RuntimeEvent:
    data = machine.data
    assert data.request is not None
    return RuntimeEvent(
        name=name,
        runtime=data.runtime,
        correlation_id=data.request.correlation_id,
        session_id=data.binding.session_id if data.binding else None,
    )


def test_new_and_resume_requests_are_distinct(tmp_path):
    env = environment(tmp_path)

    with pytest.raises(ValidationError):
        request(env, SessionOpenMode.NEW, "session-1")
    with pytest.raises(ValidationError):
        request(env, SessionOpenMode.RESUME)


def test_new_session_resolves_and_records_environment_binding(tmp_path):
    catalog = RuntimeSessionBindingCatalog()
    coordinator = RuntimeSessionCoordinator(catalog)
    identity = runtime()
    env = environment(tmp_path)

    machine = coordinator.open(identity, request(env))

    assert machine.data.state is SessionState.RESOLVING
    binding = coordinator.resolve_new(machine, "session-1")
    assert machine.data.state is SessionState.READY
    assert binding.environment == env
    assert binding.origin is SessionOpenMode.NEW
    assert binding.parent_session_id is None
    assert catalog.find(identity, "session-1") == binding


def test_resume_requires_known_session_and_matching_environment(tmp_path):
    catalog = RuntimeSessionBindingCatalog()
    coordinator = RuntimeSessionCoordinator(catalog)
    identity = runtime()
    env = environment(tmp_path)
    created = coordinator.open(identity, request(env))
    binding = coordinator.resolve_new(created, "session-1")

    resumed = coordinator.open(
        identity,
        request(env, SessionOpenMode.RESUME, "session-1"),
    )

    assert resumed.data.state is SessionState.READY
    assert resumed.data.binding == binding
    assert resumed.data.binding.origin is SessionOpenMode.NEW


def test_unknown_session_fails_without_runtime_resolution(tmp_path):
    coordinator = RuntimeSessionCoordinator(RuntimeSessionBindingCatalog())

    machine = coordinator.open(
        runtime(),
        request(environment(tmp_path), SessionOpenMode.RESUME, "missing"),
    )

    assert machine.data.state is SessionState.FAILED
    assert machine.data.failure is not None
    assert machine.data.failure.code is RuntimeFailureCode.SESSION_NOT_FOUND


def test_environment_mismatch_blocks_resume(tmp_path):
    catalog = RuntimeSessionBindingCatalog()
    coordinator = RuntimeSessionCoordinator(catalog)
    identity = runtime()
    original = environment(tmp_path / "original")
    other = environment(tmp_path / "other", "env-other")
    created = coordinator.open(identity, request(original))
    coordinator.resolve_new(created, "session-1")

    resumed = coordinator.open(
        identity,
        request(other, SessionOpenMode.RESUME, "session-1"),
    )

    assert resumed.data.state is SessionState.FAILED
    assert resumed.data.failure is not None
    assert resumed.data.failure.code is RuntimeFailureCode.ENVIRONMENT_MISMATCH


def test_catalog_refuses_rebinding_same_runtime_session(tmp_path):
    catalog = RuntimeSessionBindingCatalog()
    coordinator = RuntimeSessionCoordinator(catalog)
    identity = runtime()
    created = coordinator.open(identity, request(environment(tmp_path)))
    binding = coordinator.resolve_new(created, "session-1")
    conflicting = RuntimeSessionBinding(
        runtime=identity,
        session_id="session-1",
        environment=environment(tmp_path / "other", "env-other"),
        origin=SessionOpenMode.NEW,
    )

    with pytest.raises(ValueError, match="already bound"):
        catalog.add(conflicting)

    assert catalog.find(identity, "session-1") == binding


def test_turn_request_cannot_change_bound_working_directory(tmp_path):
    identity = runtime()
    env = environment(tmp_path / "original")
    binding = RuntimeSessionBinding(
        runtime=identity,
        session_id="session-1",
        environment=env,
        origin=SessionOpenMode.NEW,
    )

    with pytest.raises(ValidationError, match="bound environment"):
        RuntimeTurnRequest(
            turn_id="turn-1",
            correlation_id="request-1",
            prompt="continue",
            working_directory=str(tmp_path / "other"),
            session=binding,
        )


def test_session_tracks_turn_busy_ready_and_close(tmp_path):
    coordinator = RuntimeSessionCoordinator(RuntimeSessionBindingCatalog())
    machine = coordinator.open(runtime(), request(environment(tmp_path)))
    coordinator.resolve_new(machine, "session-1")

    machine.apply(session_event(machine, SessionEvent.SESSION_BECAME_BUSY))
    assert machine.data.state is SessionState.BUSY
    machine.apply(session_event(machine, SessionEvent.SESSION_BECAME_READY))
    assert machine.data.state is SessionState.READY
    machine.apply(session_event(machine, SessionEvent.SESSION_CLOSE_STARTED))
    assert machine.data.state is SessionState.CLOSING
    machine.apply(session_event(machine, SessionEvent.SESSION_CLOSED))
    assert machine.data.state is SessionState.CLOSED


def test_invalid_context_does_not_mutate_state(tmp_path):
    coordinator = RuntimeSessionCoordinator(RuntimeSessionBindingCatalog())
    machine = coordinator.open(runtime(), request(environment(tmp_path)))
    coordinator.resolve_new(machine, "session-1")
    before = machine.data
    invalid = session_event(machine, SessionEvent.SESSION_BECAME_BUSY).model_copy(
        update={"correlation_id": "another-request"}
    )

    with pytest.raises(InvalidSessionTransition):
        machine.apply(invalid)

    assert machine.data == before


def test_session_and_catalog_state_round_trip(tmp_path):
    catalog = RuntimeSessionBindingCatalog()
    coordinator = RuntimeSessionCoordinator(catalog)
    machine = coordinator.open(runtime(), request(environment(tmp_path)))
    coordinator.resolve_new(machine, "session-1")

    restored_state = SessionStateData.model_validate_json(
        machine.data.model_dump_json()
    )
    restored_catalog_state = SessionBindingCatalogState.model_validate_json(
        catalog.state.model_dump_json()
    )
    restored_machine = SessionMachine(restored_state)
    restored_catalog = RuntimeSessionBindingCatalog(restored_catalog_state)

    assert restored_machine.data == machine.data
    assert restored_catalog.find(runtime(), "session-1") is not None


def test_persisted_catalog_rejects_duplicate_session_identity(tmp_path):
    catalog = RuntimeSessionBindingCatalog()
    coordinator = RuntimeSessionCoordinator(catalog)
    machine = coordinator.open(runtime(), request(environment(tmp_path)))
    binding = coordinator.resolve_new(machine, "session-1")

    with pytest.raises(ValidationError, match="duplicate"):
        SessionBindingCatalogState(bindings=(binding, binding))


def test_lost_session_records_structured_failure(tmp_path):
    coordinator = RuntimeSessionCoordinator(RuntimeSessionBindingCatalog())
    machine = coordinator.open(runtime(), request(environment(tmp_path)))
    coordinator.resolve_new(machine, "session-1")
    event = session_event(machine, SessionEvent.SESSION_LOST).model_copy(
        update={
            "payload": {
                "failure": RuntimeFailure(
                    code=RuntimeFailureCode.SESSION_NOT_FOUND,
                    message="session disappeared",
                ).model_dump(mode="json")
            }
        }
    )

    machine.apply(event)

    assert machine.data.state is SessionState.FAILED
    assert machine.data.failure is not None
    assert machine.data.failure.code is RuntimeFailureCode.SESSION_NOT_FOUND
