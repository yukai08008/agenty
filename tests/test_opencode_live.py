import os
from pathlib import Path

import pytest

from agenty.runtime.machine import RuntimeProbeMachine
from agenty.runtime.opencode import OpenCodeRuntimeAdapter
from agenty.runtime.protocol import (
    AvailabilityState,
    OutputEvent,
    RuntimeTurnRequest,
    TurnState,
)
from agenty.runtime.runner import RuntimeTurnRunner


@pytest.mark.skipif(
    os.environ.get("AGENTY_LIVE_OPENCODE") != "1",
    reason="real OpenCode model call requires explicit opt-in",
)
def test_live_opencode_free_model_smoke():
    model = os.environ.get(
        "AGENTY_LIVE_OPENCODE_MODEL",
        "opencode/nemotron-3.5-lightning-free",
    )
    workspace = Path(__file__).parents[1].resolve()
    adapter = OpenCodeRuntimeAdapter(timeout_seconds=120)
    runtime_snapshot = RuntimeProbeMachine(adapter).probe(
        correlation_id="live-opencode-probe"
    )
    assert runtime_snapshot.availability is AvailabilityState.AVAILABLE

    result = RuntimeTurnRunner(adapter, runtime_snapshot.runtime).run(
        RuntimeTurnRequest(
            turn_id="live-smoke-turn",
            correlation_id="live-smoke-request",
            prompt=(
                "Do not use tools. Reply with exactly this text and nothing else: "
                "AGENTY_SMOKE_OK"
            ),
            working_directory=str(workspace),
            model=model,
        )
    )

    assert result.state is TurnState.SUCCEEDED, result.failure
    assert result.session_id
    response = "".join(
        event.payload.get("text", "")
        for event in result.events
        if event.name is OutputEvent.TEXT_EMITTED
    )
    assert "AGENTY_SMOKE_OK" in response
