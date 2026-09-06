"""Provider-neutral SessionMachine and environment binding catalog."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agenty.runtime.protocol import (
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeSessionBinding,
    RuntimeSessionRequest,
    SessionEvent,
    SessionOpenMode,
    SessionState,
)


class InvalidSessionTransition(RuntimeError):
    pass


class SessionStateData(BaseModel):
    """Serializable state owned by one SessionMachine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime: RuntimeIdentity
    state: SessionState = SessionState.NONE
    request: RuntimeSessionRequest | None = None
    binding: RuntimeSessionBinding | None = None
    failure: RuntimeFailure | None = None
    events: tuple[RuntimeEvent, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_state_shape(self) -> "SessionStateData":
        if self.state is SessionState.NONE:
            if self.request is not None or self.binding is not None:
                raise ValueError("empty session state cannot hold context")
        elif self.state is SessionState.RESOLVING:
            if self.request is None or self.binding is not None:
                raise ValueError("resolving session requires only a request")
        elif self.state in {
            SessionState.READY,
            SessionState.BUSY,
            SessionState.CLOSING,
            SessionState.CLOSED,
        }:
            if self.request is None or self.binding is None:
                raise ValueError("resolved session requires request and binding")
        elif self.state is SessionState.FAILED and self.failure is None:
            raise ValueError("failed session requires failure")
        return self


class SessionBindingCatalogState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    bindings: tuple[RuntimeSessionBinding, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_unique_bindings(self) -> "SessionBindingCatalogState":
        keys: set[tuple[str, str | None, str, str]] = set()
        for binding in self.bindings:
            key = RuntimeSessionBindingCatalog._key(
                binding.runtime, binding.session_id
            )
            if key in keys:
                raise ValueError("duplicate runtime session binding")
            keys.add(key)
        return self


class RuntimeSessionBindingCatalog:
    """In-memory boundary; its Pydantic state can be persisted by the app."""

    def __init__(self, state: SessionBindingCatalogState | None = None) -> None:
        self._state = state or SessionBindingCatalogState()

    @property
    def state(self) -> SessionBindingCatalogState:
        return self._state

    def find(
        self, runtime: RuntimeIdentity, session_id: str
    ) -> RuntimeSessionBinding | None:
        key = self._key(runtime, session_id)
        return next(
            (
                binding
                for binding in self._state.bindings
                if self._key(binding.runtime, binding.session_id) == key
            ),
            None,
        )

    def add(self, binding: RuntimeSessionBinding) -> None:
        existing = self.find(binding.runtime, binding.session_id)
        if existing is not None:
            if existing != binding:
                raise ValueError(
                    "session identity is already bound to another context"
                )
            return
        self._state = self._state.model_copy(
            update={"bindings": (*self._state.bindings, binding)}
        )

    @staticmethod
    def _key(
        runtime: RuntimeIdentity, session_id: str
    ) -> tuple[str, str | None, str, str]:
        return (
            runtime.runtime_kind,
            runtime.runtime_version,
            runtime.runtime_id,
            session_id,
        )


class SessionMachine:
    def __init__(self, state: SessionStateData) -> None:
        self._data = state

    @classmethod
    def create(cls, runtime: RuntimeIdentity) -> "SessionMachine":
        return cls(SessionStateData(runtime=runtime))

    @property
    def data(self) -> SessionStateData:
        return self._data

    def apply(self, event: RuntimeEvent) -> SessionStateData:
        self._validate_context(event)
        next_data = self._transition(event)
        self._data = next_data.model_copy(
            update={"events": (*next_data.events, event)}
        )
        return self._data

    def _transition(self, event: RuntimeEvent) -> SessionStateData:
        state = self._data.state
        name = event.name

        if name is SessionEvent.SESSION_RESOLUTION_STARTED and state in {
            SessionState.NONE,
            SessionState.FAILED,
        }:
            request = self._payload_model(event, "request", RuntimeSessionRequest)
            if event.correlation_id != request.correlation_id:
                raise InvalidSessionTransition(
                    "request correlation does not match event"
                )
            return SessionStateData(
                runtime=self._data.runtime,
                state=SessionState.RESOLVING,
                request=request,
                events=self._data.events,
            )
        if name is SessionEvent.SESSION_RESOLVED and state is SessionState.RESOLVING:
            binding = self._payload_model(
                event, "binding", RuntimeSessionBinding
            )
            self._validate_binding(binding, event)
            return self._data.model_copy(
                update={
                    "state": SessionState.READY,
                    "binding": binding,
                    "failure": None,
                }
            )
        if (
            name is SessionEvent.SESSION_RESOLUTION_FAILED
            and state is SessionState.RESOLVING
        ):
            failure = self._payload_model(event, "failure", RuntimeFailure)
            return self._data.model_copy(
                update={"state": SessionState.FAILED, "failure": failure}
            )
        if name is SessionEvent.SESSION_BECAME_BUSY and state is SessionState.READY:
            return self._data.model_copy(update={"state": SessionState.BUSY})
        if name is SessionEvent.SESSION_BECAME_READY and state is SessionState.BUSY:
            return self._data.model_copy(update={"state": SessionState.READY})
        if name is SessionEvent.SESSION_LOST and state in {
            SessionState.READY,
            SessionState.BUSY,
        }:
            failure = self._payload_model(event, "failure", RuntimeFailure)
            return self._data.model_copy(
                update={"state": SessionState.FAILED, "failure": failure}
            )
        if name is SessionEvent.SESSION_CLOSE_STARTED and state is SessionState.READY:
            return self._data.model_copy(update={"state": SessionState.CLOSING})
        if name is SessionEvent.SESSION_CLOSED and state is SessionState.CLOSING:
            return self._data.model_copy(update={"state": SessionState.CLOSED})
        raise InvalidSessionTransition(
            f"cannot apply {name!s} while session is {state.value}"
        )

    def _validate_context(self, event: RuntimeEvent) -> None:
        if not isinstance(event.name, SessionEvent):
            raise InvalidSessionTransition("event is not a Session event")
        if event.runtime != self._data.runtime:
            raise InvalidSessionTransition("runtime context changed")
        if self._data.request is not None:
            if event.correlation_id != self._data.request.correlation_id:
                raise InvalidSessionTransition("correlation context changed")
        if self._data.binding is not None:
            if event.session_id != self._data.binding.session_id:
                raise InvalidSessionTransition("session context changed")

    def _validate_binding(
        self, binding: RuntimeSessionBinding, event: RuntimeEvent
    ) -> None:
        request = self._data.request
        assert request is not None
        if binding.runtime != self._data.runtime:
            raise InvalidSessionTransition("binding runtime does not match")
        if binding.environment != request.environment:
            raise InvalidSessionTransition("binding environment does not match")
        if event.session_id != binding.session_id:
            raise InvalidSessionTransition("resolved event session does not match")
        if (
            request.mode is SessionOpenMode.RESUME
            and request.session_id != binding.session_id
        ):
            raise InvalidSessionTransition("requested session does not match")

    @staticmethod
    def _payload_model(event: RuntimeEvent, key: str, model_type):
        value = event.payload.get(key)
        if value is None:
            raise InvalidSessionTransition(f"event requires payload.{key}")
        try:
            return model_type.model_validate(value)
        except ValueError as exc:
            raise InvalidSessionTransition(
                f"invalid payload.{key}: {exc}"
            ) from exc


class RuntimeSessionCoordinator:
    """Resolves public new/resume requests without exposing vendor commands."""

    def __init__(self, catalog: RuntimeSessionBindingCatalog) -> None:
        self.catalog = catalog

    def open(
        self, runtime: RuntimeIdentity, request: RuntimeSessionRequest
    ) -> SessionMachine:
        machine = SessionMachine.create(runtime)
        machine.apply(
            self._event(
                SessionEvent.SESSION_RESOLUTION_STARTED,
                runtime,
                request,
                payload={"request": request.model_dump(mode="json")},
            )
        )
        if request.mode is SessionOpenMode.NEW:
            return machine

        assert request.session_id is not None
        binding = self.catalog.find(runtime, request.session_id)
        if binding is None:
            self._fail(
                machine,
                RuntimeFailureCode.SESSION_NOT_FOUND,
                "runtime session has no known environment binding",
            )
        elif binding.environment != request.environment:
            self._fail(
                machine,
                RuntimeFailureCode.ENVIRONMENT_MISMATCH,
                "runtime session is bound to a different environment",
            )
        else:
            machine.apply(
                self._event(
                    SessionEvent.SESSION_RESOLVED,
                    runtime,
                    request,
                    session_id=binding.session_id,
                    payload={"binding": binding.model_dump(mode="json")},
                )
            )
        return machine

    def resolve_new(
        self, machine: SessionMachine, session_id: str
    ) -> RuntimeSessionBinding:
        request = machine.data.request
        if machine.data.state is not SessionState.RESOLVING or request is None:
            raise InvalidSessionTransition("new session is not resolving")
        if request.mode is not SessionOpenMode.NEW:
            raise InvalidSessionTransition("request is not creating a session")
        binding = RuntimeSessionBinding(
            runtime=machine.data.runtime,
            session_id=session_id,
            environment=request.environment,
            origin=SessionOpenMode.NEW,
        )
        self.catalog.add(binding)
        machine.apply(
            self._event(
                SessionEvent.SESSION_RESOLVED,
                machine.data.runtime,
                request,
                session_id=session_id,
                payload={"binding": binding.model_dump(mode="json")},
            )
        )
        return binding

    def _fail(
        self,
        machine: SessionMachine,
        code: RuntimeFailureCode,
        message: str,
    ) -> None:
        request = machine.data.request
        assert request is not None
        failure = RuntimeFailure(code=code, message=message)
        machine.apply(
            self._event(
                SessionEvent.SESSION_RESOLUTION_FAILED,
                machine.data.runtime,
                request,
                session_id=request.session_id,
                payload={"failure": failure.model_dump(mode="json")},
            )
        )

    @staticmethod
    def _event(
        name: SessionEvent,
        runtime: RuntimeIdentity,
        request: RuntimeSessionRequest,
        *,
        session_id: str | None = None,
        payload: dict | None = None,
    ) -> RuntimeEvent:
        return RuntimeEvent(
            name=name,
            runtime=runtime,
            correlation_id=request.correlation_id,
            session_id=session_id,
            payload=payload or {},
        )
