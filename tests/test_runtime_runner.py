from agenty.runtime.protocol import (
    ChannelMode,
    RuntimeEvent,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeTurnRequest,
    TurnEvent,
    TurnState,
)
from agenty.runtime.runner import RuntimeTurnRunner


def test_invalid_adapter_lifecycle_becomes_invalid_output_failure():
    runtime = RuntimeIdentity(
        runtime_id="local-fake",
        runtime_kind="fake",
        runtime_version="1.2.3",
        channel=ChannelMode.TRANSIENT_PROCESS,
    )
    request = RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt="hello",
        working_directory="/tmp/project",
    )

    class InvalidLifecycleAdapter:
        def iter_turn_events(self, runtime, request):
            yield RuntimeEvent(
                name=TurnEvent.TURN_SUCCEEDED,
                runtime=runtime,
                correlation_id=request.correlation_id,
                turn_id=request.turn_id,
            )

    runner = RuntimeTurnRunner(InvalidLifecycleAdapter(), runtime)

    result = runner.run(request)

    assert result.state is TurnState.FAILED
    assert result.failure is not None
    assert result.failure.code is RuntimeFailureCode.INVALID_OUTPUT
    stream = runner.last_event_stream
    assert stream is not None
    assert [event.sequence for event in stream.events] == [1, 2, 3, 4]
