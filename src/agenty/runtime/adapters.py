"""Adapter boundary used by RuntimeMachine."""

from __future__ import annotations

from typing import Protocol

from agenty.runtime.models import RuntimeFailure, RuntimeInfo


class RuntimeAdapterError(RuntimeError):
    def __init__(self, failure: RuntimeFailure):
        self.failure = failure
        super().__init__(failure.message)


class RuntimeAdapter(Protocol):
    """Smallest adapter contract needed by the first Runtime slice."""

    @property
    def runtime_id(self) -> str:
        ...

    def probe(self) -> RuntimeInfo:
        ...
