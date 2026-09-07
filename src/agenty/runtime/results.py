"""Turn result aggregation, failure classification, and evidence storage."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from agenty.runtime.events import RuntimeEventStreamStateData
from agenty.runtime.protocol import (
    ArtifactManifest,
    EventLogRef,
    OutputEvent,
    RuntimeArtifact,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeUsage,
    TurnResult,
)
from agenty.runtime.turn import TurnStateData

_IGNORED_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache"}


class WorkspaceSnapshot:
    def __init__(
        self,
        root: Path,
        files: dict[str, str],
        *,
        available: bool = True,
        scan_complete: bool = True,
    ) -> None:
        self.root = root
        self.files = files
        self.available = available
        self.scan_complete = scan_complete

    @classmethod
    def unavailable(cls, directory: str) -> "WorkspaceSnapshot":
        return cls(
            Path(directory).expanduser().absolute(),
            {},
            available=False,
            scan_complete=False,
        )

    @classmethod
    def capture(cls, directory: str) -> "WorkspaceSnapshot":
        root = Path(directory).resolve()
        files = {}
        paths, scan_complete = _workspace_files(root)
        for path in paths:
            try:
                files[path.relative_to(root).as_posix()] = _digest(path)
            except OSError:
                scan_complete = False
                continue
        return cls(root, files, scan_complete=scan_complete)

    def manifest(self) -> ArtifactManifest:
        if not self.available:
            return ArtifactManifest(
                root_directory=str(self.root),
                scan_complete=False,
            )
        artifacts = []
        paths, scan_complete = _workspace_files(self.root)
        scan_complete = scan_complete and self.scan_complete
        for path in paths:
            relative = path.relative_to(self.root).as_posix()
            try:
                digest = _digest(path)
                size_bytes = path.stat().st_size
            except OSError:
                scan_complete = False
                continue
            if self.files.get(relative) == digest:
                continue
            media_type = mimetypes.guess_type(path.name)[0] or (
                "application/octet-stream"
            )
            artifacts.append(
                RuntimeArtifact(
                    path=relative,
                    media_type=media_type,
                    size_bytes=size_bytes,
                    sha256=digest,
                    producer="unknown:filesystem_observation",
                )
            )
        return ArtifactManifest(
            root_directory=str(self.root),
            artifacts=tuple(sorted(artifacts, key=lambda item: item.path)),
            scan_complete=scan_complete,
        )


class RuntimeResultCollector:
    def __init__(self, event_log_directory: str | None = None) -> None:
        directory = event_log_directory or str(
            Path(tempfile.gettempdir()) / "agenty-event-logs"
        )
        self.event_log_directory = Path(directory).expanduser().absolute()

    def build(
        self,
        runtime: RuntimeIdentity,
        turn: TurnStateData,
        stream: RuntimeEventStreamStateData,
        before: WorkspaceSnapshot,
    ) -> TurnResult:
        assert turn.state is not None
        return TurnResult(
            runtime=runtime,
            turn_id=turn.request.turn_id,
            correlation_id=turn.request.correlation_id,
            request=turn.request,
            state=turn.state,
            session_id=turn.session_id,
            output_text="".join(
                str(event.payload.get("text", ""))
                for event in turn.events
                if event.name is OutputEvent.TEXT_EMITTED
            ),
            usage=aggregate_usage(turn.events),
            failure=turn.failure,
            artifacts=before.manifest(),
            event_log=self._write_event_logs(
                runtime,
                turn.request.correlation_id,
                turn.request.turn_id,
                stream,
            ),
            events=tuple(turn.events),
        )

    def _write_event_logs(
        self,
        runtime: RuntimeIdentity,
        correlation_id: str,
        turn_id: str,
        stream: RuntimeEventStreamStateData,
    ) -> EventLogRef:
        try:
            return self._write_event_logs_to(
                self.event_log_directory,
                runtime,
                correlation_id,
                turn_id,
                stream,
            )
        except (OSError, TypeError, ValueError):
            fallback = Path(tempfile.mkdtemp(prefix="agenty-event-logs-"))
            return self._write_event_logs_to(
                fallback,
                runtime,
                correlation_id,
                turn_id,
                stream,
            )

    def _write_event_logs_to(
        self,
        directory: Path,
        runtime: RuntimeIdentity,
        correlation_id: str,
        turn_id: str,
        stream: RuntimeEventStreamStateData,
    ) -> EventLogRef:
        if directory.is_symlink():
            raise ValueError("event log directory must not be a symlink")
        directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink():
            raise ValueError("event log directory must not be a symlink")
        execution_key = hashlib.sha256(
            f"{runtime.runtime_id}\0{correlation_id}\0{turn_id}".encode()
        ).hexdigest()[:16]
        execution_directory = directory / (
            f"{execution_key}-{uuid4().hex}"
        )
        execution_directory.mkdir(mode=0o700)
        try:
            normalized_path = execution_directory / "normalized.jsonl"
            raw_path = execution_directory / "raw.jsonl"
            normalized_content = "".join(
                json.dumps(
                    event.model_dump(mode="json"),
                    allow_nan=False,
                    sort_keys=True,
                )
                + "\n"
                for event in stream.events
            )
            raw_content = "".join(
                json.dumps(
                    record.model_dump(mode="json"),
                    allow_nan=False,
                    sort_keys=True,
                )
                + "\n"
                for record in stream.raw_events
            )
            self._write_exclusive(normalized_path, normalized_content)
            self._write_exclusive(raw_path, raw_content)
            return EventLogRef(
                normalized_path=str(normalized_path),
                normalized_sha256=_digest(normalized_path),
                normalized_event_count=len(stream.events),
                raw_path=str(raw_path),
                raw_sha256=_digest(raw_path),
                raw_event_count=len(stream.raw_events),
            )
        except (OSError, TypeError, ValueError):
            shutil.rmtree(execution_directory, ignore_errors=True)
            raise

    @staticmethod
    def _write_exclusive(path: Path, content: str) -> None:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()


def aggregate_usage(events: list[RuntimeEvent]) -> RuntimeUsage:
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    cost = Decimal(0)
    references = []
    for event in events:
        if event.name is not OutputEvent.USAGE_REPORTED:
            continue
        validate_usage_event(event)
        for key in totals:
            totals[key] += event.payload.get(key, 0)
        cost += Decimal(str(event.payload.get("cost", 0)))
        reference = event.payload.get("provider_reference")
        if isinstance(reference, str) and reference and reference not in references:
            references.append(reference)
    return RuntimeUsage(
        **totals,
        total_tokens=sum(totals.values()),
        cost=cost,
        provider_references=tuple(references),
    )


def validate_usage_event(event: RuntimeEvent) -> None:
    if event.name is not OutputEvent.USAGE_REPORTED:
        return
    for field in (
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
    ):
        value = event.payload.get(field, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    raw_cost = event.payload.get("cost", 0)
    try:
        cost = Decimal(str(raw_cost))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("cost must be a non-negative finite number") from exc
    if not cost.is_finite() or cost < 0:
        raise ValueError("cost must be a non-negative finite number")
    reference = event.payload.get("provider_reference")
    if reference is not None and (
        not isinstance(reference, str) or not reference.strip()
    ):
        raise ValueError("provider_reference must be non-empty text")


def classify_failure(failure: RuntimeFailure) -> RuntimeFailure:
    if failure.code in {
        RuntimeFailureCode.RATE_LIMITED,
        RuntimeFailureCode.QUOTA_EXHAUSTED,
        RuntimeFailureCode.AUTHENTICATION_FAILED,
        RuntimeFailureCode.MODEL_UNAVAILABLE,
        RuntimeFailureCode.TURN_TIMEOUT,
        RuntimeFailureCode.RUNTIME_CRASH,
        RuntimeFailureCode.INVALID_OUTPUT,
    }:
        return failure
    details = failure.details
    status = details.get("status_code")
    text = " ".join(
        str(value).lower()
        for value in (
            details.get("error_type"),
            details.get("message"),
            details.get("reason"),
            failure.message,
        )
        if value
    )
    code = failure.code
    retryable = failure.retryable
    compact = "".join(character for character in text if character.isalnum())
    observed_retryable = details.get("retryable")
    if isinstance(observed_retryable, bool):
        retryable = observed_retryable
    reason = str(details.get("reason", "")).lower()
    if reason in {"freeusagelimiterror", "gousagelimiterror"}:
        code = RuntimeFailureCode.RATE_LIMITED
        if retryable is None:
            retryable = True
    elif reason == "providerautherror":
        code = RuntimeFailureCode.AUTHENTICATION_FAILED
        retryable = False
    elif reason in {"modelnotfounderror", "modelunavailableerror"}:
        code = RuntimeFailureCode.MODEL_UNAVAILABLE
        retryable = False
    elif reason == "quotaexceedederror" or "quota" in text or "credit" in text:
        code = RuntimeFailureCode.QUOTA_EXHAUSTED
        retryable = False
    elif (
        status in {401, 403}
        or "authentication" in text
        or "unauthorized" in text
        or "autherror" in compact
        or "providerauth" in compact
    ):
        code = RuntimeFailureCode.AUTHENTICATION_FAILED
        retryable = False
    elif (
        status == 429
        or "rate limit" in text
        or "usage limit" in text
        or "usagelimit" in compact
        or "ratelimit" in compact
    ):
        code = RuntimeFailureCode.RATE_LIMITED
        if retryable is None:
            retryable = True
    elif "model" in text and (
        any(marker in text for marker in ("not found", "unavailable", "unsupported"))
        or any(
            marker in compact
            for marker in ("modelnotfound", "modelunavailable", "modelunsupported")
        )
    ):
        code = RuntimeFailureCode.MODEL_UNAVAILABLE
        retryable = False
    elif "returncode" in details:
        code = RuntimeFailureCode.RUNTIME_CRASH
        retryable = False
    return failure.model_copy(update={"code": code, "retryable": retryable})


def _workspace_files(root: Path):
    if not root.is_dir():
        return (), False
    try:
        files = tuple(
            path
            for path in root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and not any(
                part in _IGNORED_PARTS for part in path.relative_to(root).parts
            )
        )
    except OSError:
        return (), False
    return files, True


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
