"""Minimal application entry point for one RuntimeMachine-backed task."""

from __future__ import annotations

import math
from pathlib import Path
from uuid import uuid4

from agenty.runtime.opencode import OpenCodeRuntimeAdapter
from agenty.runtime.protocol import (
    InteractionPolicyMode,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeInteractionPolicy,
    RuntimeTarget,
    RuntimeTurnRequest,
    TurnResult,
)
from agenty.runtime.runner import RuntimeTurnRunner
from agenty.runtime.selection import (
    RuntimeAdapterRegistry,
    RuntimeSelectionMachine,
    RuntimeSelectionState,
)

OPENCODE_RUNTIME_VERSION = "1.18.26"


class AgentyRunError(RuntimeError):
    """Failure before a Runtime Turn can produce a TurnResult."""

    def __init__(self, failure: RuntimeFailure) -> None:
        self.failure = failure
        super().__init__(failure.message)


def run_opencode_task(
    prompt: str,
    *,
    working_directory: str = ".",
    auto_approve: bool = False,
    timeout_seconds: float = 300,
    executable: str = "opencode",
) -> TurnResult:
    """Select OpenCode 1.18.26 and execute one auditable runtime turn."""
    if not prompt.strip():
        raise AgentyRunError(
            RuntimeFailure(
                code=RuntimeFailureCode.TURN_REJECTED,
                message="task must not be empty",
            )
        )
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise AgentyRunError(
            RuntimeFailure(
                code=RuntimeFailureCode.TURN_REJECTED,
                message="timeout_seconds must be positive and finite",
            )
        )
    execution_id = uuid4().hex
    target = RuntimeTarget(
        runtime_kind="opencode",
        runtime_version=OPENCODE_RUNTIME_VERSION,
    )
    adapter = OpenCodeRuntimeAdapter(
        executable=executable,
        timeout_seconds=timeout_seconds,
    )
    registry = RuntimeAdapterRegistry()
    registry.register(target, lambda: adapter)
    selected = RuntimeSelectionMachine(registry).select(
        target,
        f"run-selection-{execution_id}",
    )
    if (
        selected.state is not RuntimeSelectionState.SELECTED
        or selected.snapshot is None
    ):
        raise AgentyRunError(
            selected.failure
            or RuntimeFailure(
                code=RuntimeFailureCode.INTERNAL,
                message="runtime selection did not produce a selected snapshot",
            )
        )

    request = RuntimeTurnRequest(
        turn_id=f"run-turn-{execution_id}",
        correlation_id=f"run-request-{execution_id}",
        prompt=prompt,
        working_directory=str(Path(working_directory).expanduser().resolve()),
        interaction=RuntimeInteractionPolicy(
            mode=(
                InteractionPolicyMode.AUTO_APPROVE
                if auto_approve
                else InteractionPolicyMode.DENY_BY_DEFAULT
            )
        ),
    )
    return RuntimeTurnRunner(
        adapter,
        selected.snapshot.runtime,
        selected.snapshot.capabilities,
    ).run(request)
