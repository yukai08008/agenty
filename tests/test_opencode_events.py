import pytest

from agenty.runtime.adapters import RuntimeTurnAdapterError
from agenty.runtime.opencode_events import OpenCodeEventNormalizer
from agenty.runtime.protocol import (
    ChannelMode,
    OutputEvent,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeTurnRequest,
)


def runtime(version: str = "1.18.26") -> RuntimeIdentity:
    return RuntimeIdentity(
        runtime_id="local-opencode",
        runtime_kind="opencode",
        runtime_version=version,
        executable="/usr/local/bin/opencode",
        channel=ChannelMode.TRANSIENT_PROCESS,
    )


def request() -> RuntimeTurnRequest:
    return RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt="hello",
        working_directory="/tmp/project",
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"type": "step_start", "part": {}}, OutputEvent.STEP_STARTED),
        ({"type": "step_finish", "part": {}}, OutputEvent.STEP_FINISHED),
        (
            {"type": "text", "part": {"text": "hello"}},
            OutputEvent.TEXT_EMITTED,
        ),
        (
            {"type": "reasoning", "part": {"text": "thinking"}},
            OutputEvent.REASONING_EMITTED,
        ),
        (
            {
                "type": "tool_use",
                "part": {"tool": "read", "state": {"status": "completed"}},
            },
            OutputEvent.TOOL_COMPLETED,
        ),
        (
            {
                "type": "tool_use",
                "part": {"tool": "write", "state": {"status": "error"}},
            },
            OutputEvent.TOOL_FAILED,
        ),
        (
            {"type": "error", "error": {"message": "failed"}},
            OutputEvent.RUNTIME_ERROR_EMITTED,
        ),
    ],
)
def test_known_opencode_events_are_normalized(raw, expected):
    raw = {**raw, "sessionID": "session-1", "vendorOnly": True}

    result = OpenCodeEventNormalizer().normalize(raw, runtime(), request())

    assert result.name is expected
    assert result.session_id == "session-1"
    assert result.turn_id == "turn-1"
    assert result.correlation_id == "request-1"
    assert "vendorOnly" not in result.payload
    assert result.raw_event == raw


def test_unknown_event_type_is_explicit_invalid_output():
    with pytest.raises(RuntimeTurnAdapterError) as caught:
        OpenCodeEventNormalizer().normalize(
            {"type": "future_event", "sessionID": "session-1"},
            runtime(),
            request(),
        )

    assert caught.value.failure.code is RuntimeFailureCode.INVALID_OUTPUT
    assert "unknown event type" in caught.value.failure.message


def test_malformed_json_is_explicit_invalid_output():
    with pytest.raises(RuntimeTurnAdapterError) as caught:
        OpenCodeEventNormalizer().normalize_json_line(
            "not-json",
            runtime(),
            request(),
            line_number=7,
        )

    assert caught.value.failure.code is RuntimeFailureCode.INVALID_OUTPUT
    assert caught.value.failure.details == {"line_number": 7}


def test_normalizer_rejects_other_runtime_version():
    with pytest.raises(RuntimeTurnAdapterError) as caught:
        OpenCodeEventNormalizer().normalize(
            {"type": "text", "sessionID": "session-1"},
            runtime("1.18.27"),
            request(),
        )

    assert caught.value.failure.code is RuntimeFailureCode.INVALID_OUTPUT
    assert caught.value.failure.details["expected_version"] == "1.18.26"
