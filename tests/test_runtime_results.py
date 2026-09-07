import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from agenty.runtime.events import RuntimeEventStreamMachine
from agenty.runtime.protocol import (
    ChannelMode,
    OutputEvent,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeTurnRequest,
    TurnEvent,
    TurnResult,
    TurnState,
)
from agenty.runtime.results import (
    RuntimeResultCollector,
    WorkspaceSnapshot,
    classify_failure,
)
from agenty.runtime.turn import TurnMachine


def runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        runtime_id="local-fake",
        runtime_kind="fake",
        runtime_version="1.2.3",
        channel=ChannelMode.TRANSIENT_PROCESS,
    )


def event(name, request, *, payload=None, raw_event=None):
    return RuntimeEvent(
        name=name,
        runtime=runtime(),
        correlation_id=request.correlation_id,
        turn_id=request.turn_id,
        session_id="session-1",
        payload=payload or {},
        raw_event=raw_event,
    )


def test_result_aggregates_output_usage_artifacts_and_event_logs(tmp_path):
    workspace = tmp_path / "project"
    logs = tmp_path / "logs"
    workspace.mkdir()
    existing = workspace / "existing.txt"
    existing.write_text("before")
    before = WorkspaceSnapshot.capture(str(workspace))
    existing.write_text("after")
    created = workspace / "created.json"
    created.write_text('{"ok": true}')
    request = RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt="hello",
        working_directory=str(workspace),
    )
    machine = TurnMachine(runtime(), request)
    stream = RuntimeEventStreamMachine(
        runtime(), request.correlation_id, turn_id=request.turn_id
    )
    stream.start()
    for item in (
        event(TurnEvent.TURN_CREATED, request),
        event(TurnEvent.TURN_SUBMISSION_STARTED, request),
        event(TurnEvent.TURN_ACCEPTED, request),
        event(OutputEvent.TEXT_EMITTED, request, payload={"text": "hello "}),
        event(OutputEvent.TEXT_EMITTED, request, payload={"text": "world"}),
        event(
            OutputEvent.USAGE_REPORTED,
            request,
            payload={
                "input_tokens": 10,
                "output_tokens": 4,
                "reasoning_tokens": 2,
                "cache_read_tokens": 3,
                "cache_write_tokens": 1,
                "cost": "0.0025",
                "provider_reference": "provider:step-1",
            },
            raw_event={"vendor": True},
        ),
        event(TurnEvent.TURN_SUCCEEDED, request),
    ):
        machine.apply(stream.append(item))
    stream.close()

    result = RuntimeResultCollector(str(logs)).build(
        runtime(), machine.snapshot(), stream.snapshot(), before
    )

    assert result.output_text == "hello world"
    assert result.usage.total_tokens == 20
    assert result.usage.cost == Decimal("0.0025")
    assert result.usage.provider_references == ("provider:step-1",)
    assert [item.path for item in result.artifacts.artifacts] == [
        "created.json",
        "existing.txt",
    ]
    created_artifact = result.artifacts.artifacts[0]
    assert created_artifact.media_type == "application/json"
    assert created_artifact.sha256 == hashlib.sha256(
        created.read_bytes()
    ).hexdigest()
    assert created_artifact.producer == "unknown:filesystem_observation"
    normalized = Path(result.event_log.normalized_path).read_text().splitlines()
    raw = Path(result.event_log.raw_path).read_text().splitlines()
    assert len(normalized) == result.event_log.normalized_event_count
    assert len(raw) == 1
    assert json.loads(raw[0])["data"] == {"vendor": True}
    restored = TurnResult.model_validate_json(result.model_dump_json())
    assert restored == result


def test_usage_constructor_round_trips_with_derived_total():
    from agenty.runtime.protocol import RuntimeUsage

    usage = RuntimeUsage(input_tokens=3, output_tokens=2)
    restored = RuntimeUsage.model_validate_json(usage.model_dump_json())

    assert usage.total_tokens == 5
    assert restored == usage


@pytest.mark.parametrize(
    ("details", "code", "retryable"),
    [
        ({"status_code": 429}, RuntimeFailureCode.RATE_LIMITED, True),
        (
            {"reason": "FreeUsageLimitError", "retryable": True},
            RuntimeFailureCode.RATE_LIMITED,
            True,
        ),
        (
            {
                "reason": "FreeUsageLimitError",
                "message": "quota exceeded",
                "status_code": 403,
                "retryable": True,
            },
            RuntimeFailureCode.RATE_LIMITED,
            True,
        ),
        (
            {"status_code": 403, "message": "quota exhausted"},
            RuntimeFailureCode.QUOTA_EXHAUSTED,
            False,
        ),
        ({"error_type": "AuthError"}, RuntimeFailureCode.AUTHENTICATION_FAILED, False),
        ({"message": "quota exhausted"}, RuntimeFailureCode.QUOTA_EXHAUSTED, False),
        ({"status_code": 401}, RuntimeFailureCode.AUTHENTICATION_FAILED, False),
        ({"message": "model unavailable"}, RuntimeFailureCode.MODEL_UNAVAILABLE, False),
        (
            {"reason": "ModelNotFoundError"},
            RuntimeFailureCode.MODEL_UNAVAILABLE,
            False,
        ),
        ({"returncode": 9}, RuntimeFailureCode.RUNTIME_CRASH, False),
    ],
)
def test_failure_classification_is_specific(details, code, retryable):
    classified = classify_failure(
        RuntimeFailure(
            code=RuntimeFailureCode.TURN_FAILED,
            message="turn failed",
            details=details,
        )
    )

    assert classified.code is code
    assert classified.retryable is retryable


def test_failure_classification_preserves_explicit_retryable_false():
    classified = classify_failure(
        RuntimeFailure(
            code=RuntimeFailureCode.TURN_FAILED,
            message="rate limit",
            retryable=False,
            details={"status_code": 429},
        )
    )

    assert classified.code is RuntimeFailureCode.RATE_LIMITED
    assert classified.retryable is False


def test_event_log_paths_are_unique_for_reused_turn_id(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    request = RuntimeTurnRequest(
        turn_id="turn/raw",
        correlation_id="request-1",
        prompt="hello",
        working_directory=str(workspace),
    )
    before = WorkspaceSnapshot.capture(str(workspace))
    machine = TurnMachine(runtime(), request)
    stream = RuntimeEventStreamMachine(
        runtime(), request.correlation_id, turn_id=request.turn_id
    )
    stream.start()
    for item in (
        event(TurnEvent.TURN_CREATED, request),
        event(TurnEvent.TURN_SUBMISSION_STARTED, request),
        event(TurnEvent.TURN_ACCEPTED, request),
        event(TurnEvent.TURN_SUCCEEDED, request),
    ):
        machine.apply(stream.append(item))
    stream.close()
    collector = RuntimeResultCollector(str(tmp_path / "logs"))

    first = collector.build(runtime(), machine.snapshot(), stream.snapshot(), before)
    second = collector.build(runtime(), machine.snapshot(), stream.snapshot(), before)

    assert first.event_log.normalized_path != second.event_log.normalized_path
    assert Path(first.event_log.normalized_path).read_text()
    assert Path(second.event_log.normalized_path).read_text()


def test_symlink_event_log_directory_uses_private_fallback(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    request = RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt="hello",
        working_directory=str(workspace),
    )
    before = WorkspaceSnapshot.capture(str(workspace))
    machine = TurnMachine(runtime(), request)
    stream = RuntimeEventStreamMachine(
        runtime(), request.correlation_id, turn_id=request.turn_id
    )
    stream.start()
    for item in (
        event(TurnEvent.TURN_CREATED, request),
        event(TurnEvent.TURN_SUBMISSION_STARTED, request),
        event(TurnEvent.TURN_ACCEPTED, request),
        event(TurnEvent.TURN_SUCCEEDED, request),
    ):
        machine.apply(stream.append(item))
    stream.close()
    target = tmp_path / "target"
    target.mkdir()
    configured = tmp_path / "logs"
    configured.symlink_to(target, target_is_directory=True)

    result = RuntimeResultCollector(str(configured)).build(
        runtime(), machine.snapshot(), stream.snapshot(), before
    )

    normalized = Path(result.event_log.normalized_path)
    assert normalized.is_file()
    assert target not in normalized.parents
    assert normalized.stat().st_mode & 0o777 == 0o600
    assert normalized.parent.stat().st_mode & 0o777 == 0o700


def test_result_restoration_rejects_mismatched_audit_context(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    request = RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt="hello",
        working_directory=str(workspace),
    )
    before = WorkspaceSnapshot.capture(str(workspace))
    machine = TurnMachine(runtime(), request)
    stream = RuntimeEventStreamMachine(
        runtime(), request.correlation_id, turn_id=request.turn_id
    )
    stream.start()
    for item in (
        event(TurnEvent.TURN_CREATED, request),
        event(TurnEvent.TURN_SUBMISSION_STARTED, request),
        event(TurnEvent.TURN_ACCEPTED, request),
        event(TurnEvent.TURN_SUCCEEDED, request),
    ):
        machine.apply(stream.append(item))
    stream.close()
    result = RuntimeResultCollector(str(tmp_path / "logs")).build(
        runtime(), machine.snapshot(), stream.snapshot(), before
    )
    serialized = result.model_dump(mode="json")
    serialized["turn_id"] = "another-turn"

    with pytest.raises(ValidationError, match="context must match"):
        TurnResult.model_validate(serialized)


def test_result_restoration_rejects_aggregate_event_contradictions(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    request = RuntimeTurnRequest(
        turn_id="turn-1",
        correlation_id="request-1",
        prompt="hello",
        working_directory=str(workspace),
    )
    before = WorkspaceSnapshot.capture(str(workspace))
    machine = TurnMachine(runtime(), request)
    stream = RuntimeEventStreamMachine(
        runtime(), request.correlation_id, turn_id=request.turn_id
    )
    stream.start()
    for item in (
        event(TurnEvent.TURN_CREATED, request),
        event(TurnEvent.TURN_SUBMISSION_STARTED, request),
        event(TurnEvent.TURN_ACCEPTED, request),
        event(OutputEvent.TEXT_EMITTED, request, payload={"text": "hello"}),
        event(TurnEvent.TURN_SUCCEEDED, request),
    ):
        machine.apply(stream.append(item))
    stream.close()
    result = RuntimeResultCollector(str(tmp_path / "logs")).build(
        runtime(), machine.snapshot(), stream.snapshot(), before
    )
    serialized = result.model_dump(mode="json")
    serialized["output_text"] = "invented"

    with pytest.raises(ValidationError, match="output must match"):
        TurnResult.model_validate(serialized)


def test_artifact_rejects_traversal_path_and_invalid_digest():
    from agenty.runtime.protocol import RuntimeArtifact

    with pytest.raises(ValidationError, match="relative"):
        RuntimeArtifact(
            path="../escape",
            media_type="text/plain",
            size_bytes=1,
            sha256="0" * 64,
            producer="unknown:filesystem_observation",
        )
    with pytest.raises(ValidationError, match="sha256"):
        RuntimeArtifact(
            path="output.txt",
            media_type="text/plain",
            size_bytes=1,
            sha256="not-a-digest",
            producer="unknown:filesystem_observation",
        )


def test_terminal_result_requires_failure_for_failed_state(tmp_path):
    from agenty.runtime.protocol import ArtifactManifest, EventLogRef

    empty = tmp_path / "empty"
    empty.write_text("")
    digest = hashlib.sha256(b"").hexdigest()
    with pytest.raises(ValidationError, match="requires failure"):
        TurnResult(
            runtime=runtime(),
            turn_id="turn-1",
            correlation_id="request-1",
            request=RuntimeTurnRequest(
                turn_id="turn-1",
                correlation_id="request-1",
                prompt="hello",
                working_directory=str(tmp_path),
            ),
            state=TurnState.FAILED,
            artifacts=ArtifactManifest(root_directory=str(tmp_path)),
            event_log=EventLogRef(
                normalized_path=str(empty),
                normalized_sha256=digest,
                normalized_event_count=0,
                raw_path=str(empty),
                raw_sha256=digest,
                raw_event_count=0,
            ),
        )
