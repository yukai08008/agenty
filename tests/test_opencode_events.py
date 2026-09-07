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


def test_step_finish_usage_is_normalized_without_vendor_fields():
    raw = {
        "type": "step_finish",
        "sessionID": "session-1",
        "part": {
            "tokens": {
                "input": 10,
                "output": 4,
                "reasoning": 2,
                "cache": {"read": 3, "write": 1},
            },
            "cost": 0.0025,
        },
    }

    event = OpenCodeEventNormalizer().usage_event(
        raw,
        runtime(),
        request(),
        line_number=7,
    )

    assert event is not None
    assert event.name is OutputEvent.USAGE_REPORTED
    assert event.payload == {
        "input_tokens": 10,
        "output_tokens": 4,
        "reasoning_tokens": 2,
        "cache_read_tokens": 3,
        "cache_write_tokens": 1,
        "cost": 0.0025,
        "provider_reference": "opencode-jsonl:7",
    }
    assert event.raw_event is None
    assert event.source_reference == "opencode-jsonl:7"


@pytest.mark.parametrize(
    ("tokens", "field"),
    [
        ({"input": -1}, "tokens.input"),
        ({"output": "4"}, "tokens.output"),
        ({"reasoning": True}, "tokens.reasoning"),
        ({"cache": {"read": -1}}, "tokens.cache.read"),
        ("bad", "tokens"),
        ({"cache": "bad"}, "tokens.cache"),
    ],
)
def test_invalid_step_finish_usage_is_not_silently_zeroed(tokens, field):
    raw = {
        "type": "step_finish",
        "sessionID": "session-1",
        "part": {"tokens": tokens},
    }

    with pytest.raises(RuntimeTurnAdapterError) as caught:
        OpenCodeEventNormalizer().usage_event(
            raw,
            runtime(),
            request(),
            line_number=7,
        )

    assert caught.value.failure.code is RuntimeFailureCode.INVALID_OUTPUT
    assert caught.value.failure.details == {"line_number": 7, "field": field}
    assert caught.value.raw_event == raw


def test_non_finite_usage_cost_is_invalid_output():
    raw = {
        "type": "step_finish",
        "sessionID": "session-1",
        "part": {"cost": float("nan")},
    }

    with pytest.raises(RuntimeTurnAdapterError) as caught:
        OpenCodeEventNormalizer().usage_event(
            raw,
            runtime(),
            request(),
            line_number=7,
        )

    assert caught.value.failure.code is RuntimeFailureCode.INVALID_OUTPUT
    assert caught.value.failure.details["field"] == "cost"


def test_opencode_error_extracts_safe_version_bound_reason():
    details = OpenCodeEventNormalizer().error_details(
        {
            "error": {
                "name": "APIError",
                "data": {
                    "message": "provider request failed",
                    "responseBody": '{"name":"FreeUsageLimitError","secret":"x"}',
                    "isRetryable": True,
                },
            }
        }
    )

    assert details == {
        "error_type": "APIError",
        "message": "provider request failed",
        "retryable": True,
        "reason": "FreeUsageLimitError",
    }
