"""Version-bound OpenCode runtime probe adapter."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

from agenty.runtime.adapters import RuntimeAdapterError, RuntimeTurnAdapterError
from agenty.runtime.protocol import (
    AvailabilityEvent,
    CapabilityRecord,
    CapabilitySupport,
    ChannelMode,
    EvidenceLevel,
    OutputEvent,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeTurnRequest,
    TurnEvent,
)


_VERSION = re.compile(r"\b\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?\b")
_SUPPORTED_VERSIONS = frozenset({"1.18.26"})

_OPTION_CAPABILITIES = {
    "--model": "model.selection",
    "--variant": "effort.selection",
    "--session": "session.resume_by_id",
    "--continue": "session.resume_latest",
    "--fork": "session.fork",
    "--interactive": "channel.interactive_window",
    "--format": "output.structured",
    "--file": "input.attachments",
}


class _ProbeCommandError(RuntimeError):
    def __init__(self, failure: RuntimeFailure) -> None:
        self.failure = failure
        super().__init__(failure.message)


class OpenCodeRuntimeAdapter:
    def __init__(
        self,
        executable: str = "opencode",
        timeout_seconds: float = 5,
        supported_versions: frozenset[str] | None = None,
    ) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.supported_versions = supported_versions or _SUPPORTED_VERSIONS

    @property
    def identity(self) -> RuntimeIdentity:
        return RuntimeIdentity(
            runtime_id="local-opencode",
            runtime_kind="opencode",
            channel=ChannelMode.TRANSIENT_PROCESS,
        )

    def detect(self) -> RuntimeIdentity:
        executable = self._resolve_executable()
        if executable is None:
            raise RuntimeAdapterError(
                AvailabilityEvent.RUNTIME_MISSING,
                RuntimeFailure(
                    code=RuntimeFailureCode.NOT_FOUND,
                    message=f"runtime executable not found: {self.executable}",
                ),
            )

        try:
            version_output = self._run_probe(executable, "--version")
        except _ProbeCommandError as exc:
            raise RuntimeAdapterError(
                AvailabilityEvent.RUNTIME_UNAVAILABLE,
                exc.failure,
            ) from exc

        match = _VERSION.search(version_output)
        if match is None:
            raise RuntimeAdapterError(
                AvailabilityEvent.RUNTIME_INCOMPATIBLE,
                RuntimeFailure(
                    code=RuntimeFailureCode.INVALID_VERSION,
                    message="OpenCode returned an unrecognized version",
                    details={"output": version_output.strip()},
                ),
            )

        version = match.group(0)
        if version not in self.supported_versions:
            raise RuntimeAdapterError(
                AvailabilityEvent.RUNTIME_INCOMPATIBLE,
                RuntimeFailure(
                    code=RuntimeFailureCode.UNSUPPORTED_VERSION,
                    message=f"unsupported OpenCode version: {version}",
                    details={"supported_versions": sorted(self.supported_versions)},
                ),
            )

        return self.identity.model_copy(
            update={"runtime_version": version, "executable": executable}
        )

    def probe_capabilities(
        self,
        runtime: RuntimeIdentity,
    ) -> tuple[CapabilityRecord, ...]:
        if runtime.runtime_kind != "opencode" or runtime.executable is None:
            raise ValueError("OpenCode capability probe requires detected identity")
        try:
            run_help = self._run_probe(runtime.executable, "run", "--help")
        except _ProbeCommandError as exc:
            raise RuntimeAdapterError(
                AvailabilityEvent.CAPABILITY_PROBE_FAILED,
                exc.failure,
            ) from exc

        records = []
        for option, capability in _OPTION_CAPABILITIES.items():
            if option not in run_help:
                continue
            constraints = ()
            if option == "--fork":
                constraints = ("requires --continue or --session",)
            elif option == "--interactive":
                constraints = ("advertised only; integration behavior unverified",)
            records.append(
                CapabilityRecord(
                    capability=capability,
                    runtime=runtime,
                    support=CapabilitySupport.UNKNOWN,
                    evidence=EvidenceLevel.ADVERTISED,
                    evidence_source="opencode run --help",
                    constraints=constraints,
                )
            )
        return tuple(records)

    def iter_turn_events(
        self,
        runtime: RuntimeIdentity,
        request: RuntimeTurnRequest,
    ) -> Iterator[RuntimeEvent]:
        self._validate_turn(runtime, request)
        command = self._turn_command(runtime, request)
        try:
            process = subprocess.Popen(
                command,
                cwd=request.working_directory,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode turn could not start",
                    details={"error": str(exc)},
                )
            ) from exc

        yield self._turn_event(TurnEvent.TURN_ACCEPTED, runtime, request)

        try:
            stdout, stderr = process.communicate(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            _, stderr = process.communicate()
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_TIMEOUT,
                    message="OpenCode turn timed out",
                    details={
                        "timeout_seconds": self.timeout_seconds,
                        "stderr": stderr.strip(),
                    },
                ),
                timed_out=True,
            ) from exc

        session_id = None
        saw_event = False
        runtime_error = None
        for line_number, line in enumerate(stdout.splitlines(), start=1):
            if not line.strip():
                continue
            raw = self._parse_json_line(line, line_number)
            saw_event = True
            event_session = raw.get("sessionID")
            if event_session is not None and (
                not isinstance(event_session, str) or not event_session.strip()
            ):
                raise self._invalid_output(
                    "OpenCode event has an invalid sessionID",
                    line_number=line_number,
                )
            if event_session:
                if session_id is not None and event_session != session_id:
                    raise self._invalid_output(
                        "OpenCode changed sessionID during one turn",
                        line_number=line_number,
                    )
                session_id = event_session

            normalized = self._normalize_output(
                raw,
                runtime,
                request,
                session_id,
                line_number,
            )
            yield normalized
            if raw.get("type") == "error":
                runtime_error = raw

        if not saw_event or session_id is None:
            raise self._invalid_output(
                "OpenCode turn produced no session-bound JSON events"
            )
        if runtime_error is not None:
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_FAILED,
                    message="OpenCode reported a runtime error",
                    details=self._error_details(runtime_error),
                )
            )
        if process.returncode != 0:
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_FAILED,
                    message="OpenCode turn exited unsuccessfully",
                    details={
                        "returncode": process.returncode,
                        "stderr": stderr.strip(),
                    },
                )
            )

        yield self._turn_event(
            TurnEvent.TURN_SUCCEEDED,
            runtime,
            request,
            session_id=session_id,
        )

    def _resolve_executable(self) -> str | None:
        candidate = Path(self.executable).expanduser()
        if candidate.parent != Path("."):
            return str(candidate.resolve()) if candidate.is_file() else None
        return shutil.which(self.executable)

    def _validate_turn(
        self,
        runtime: RuntimeIdentity,
        request: RuntimeTurnRequest,
    ) -> None:
        if (
            runtime.runtime_kind != "opencode"
            or runtime.runtime_version not in self.supported_versions
            or runtime.executable is None
        ):
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="turn requires a detected, supported OpenCode runtime",
                )
            )
        if not Path(request.working_directory).is_dir():
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="turn working directory does not exist",
                    details={"working_directory": request.working_directory},
                )
            )

    def _turn_command(
        self,
        runtime: RuntimeIdentity,
        request: RuntimeTurnRequest,
    ) -> list[str]:
        assert runtime.executable is not None
        command = [
            runtime.executable,
            "run",
            "--format",
            "json",
            "--dir",
            request.working_directory,
        ]
        if request.model is not None:
            command.extend(("--model", request.model))
        if request.effort is not None:
            command.extend(("--variant", request.effort))
        command.extend(("--", request.prompt))
        return command

    def _parse_json_line(self, line: str, line_number: int) -> dict:
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise self._invalid_output(
                "OpenCode emitted malformed JSON",
                line_number=line_number,
            ) from exc
        if not isinstance(raw, dict):
            raise self._invalid_output(
                "OpenCode JSON event must be an object",
                line_number=line_number,
            )
        return raw

    def _normalize_output(
        self,
        raw: dict,
        runtime: RuntimeIdentity,
        request: RuntimeTurnRequest,
        session_id: str | None,
        line_number: int,
    ) -> RuntimeEvent:
        event_type = raw.get("type")
        event_names = {
            "step_start": OutputEvent.STEP_STARTED,
            "step_finish": OutputEvent.STEP_FINISHED,
            "text": OutputEvent.TEXT_EMITTED,
            "reasoning": OutputEvent.REASONING_EMITTED,
            "error": OutputEvent.RUNTIME_ERROR_EMITTED,
        }
        part = raw.get("part")
        if event_type == "tool_use":
            tool_state = part.get("state") if isinstance(part, dict) else None
            status = (
                tool_state.get("status") if isinstance(tool_state, dict) else None
            )
            name = (
                OutputEvent.TOOL_FAILED
                if status == "error"
                else OutputEvent.TOOL_COMPLETED
            )
        else:
            name = event_names.get(event_type)
        if name is None:
            raise self._invalid_output(
                f"OpenCode emitted unknown event type: {event_type!r}",
                line_number=line_number,
            )
        payload = {}
        if name in {OutputEvent.TEXT_EMITTED, OutputEvent.REASONING_EMITTED}:
            text = part.get("text") if isinstance(part, dict) else None
            if isinstance(text, str):
                payload["text"] = text
        if name in {OutputEvent.TOOL_COMPLETED, OutputEvent.TOOL_FAILED}:
            if isinstance(part, dict) and isinstance(part.get("tool"), str):
                payload["tool"] = part["tool"]
        if name is OutputEvent.RUNTIME_ERROR_EMITTED:
            payload.update(self._error_details(raw))
        return RuntimeEvent(
            name=name,
            runtime=runtime,
            correlation_id=request.correlation_id,
            turn_id=request.turn_id,
            session_id=session_id,
            payload=payload,
            raw_event=raw,
        )

    def _invalid_output(self, message: str, **details) -> RuntimeTurnAdapterError:
        return RuntimeTurnAdapterError(
            RuntimeFailure(
                code=RuntimeFailureCode.INVALID_OUTPUT,
                message=message,
                details=details,
            )
        )

    def _error_text(self, raw: dict) -> str:
        return self._error_details(raw)["message"]

    def _error_details(self, raw: dict) -> dict:
        error = raw.get("error")
        if isinstance(error, str):
            return {"message": error}
        if isinstance(error, dict):
            data = error.get("data")
            details = {}
            if isinstance(error.get("name"), str):
                details["error_type"] = error["name"]
            if isinstance(data, dict):
                if isinstance(data.get("message"), str):
                    details["message"] = data["message"]
                if isinstance(data.get("statusCode"), int):
                    details["status_code"] = data["statusCode"]
                if isinstance(data.get("isRetryable"), bool):
                    details["retryable"] = data["isRetryable"]
            if "message" not in details and isinstance(error.get("message"), str):
                details["message"] = error["message"]
            if "message" not in details and "error_type" in details:
                details["message"] = details["error_type"]
            if details:
                return details
        return {"message": "OpenCode runtime error"}

    def _turn_event(
        self,
        name: TurnEvent,
        runtime: RuntimeIdentity,
        request: RuntimeTurnRequest,
        *,
        session_id: str | None = None,
    ) -> RuntimeEvent:
        return RuntimeEvent(
            name=name,
            runtime=runtime,
            correlation_id=request.correlation_id,
            turn_id=request.turn_id,
            session_id=session_id,
        )

    def _run_probe(self, executable: str, *args: str) -> str:
        try:
            result = subprocess.run(
                [executable, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise _ProbeCommandError(
                RuntimeFailure(
                    code=RuntimeFailureCode.PROBE_TIMEOUT,
                    message="OpenCode probe timed out",
                    details={"timeout_seconds": self.timeout_seconds},
                )
            ) from exc
        except OSError as exc:
            raise _ProbeCommandError(
                RuntimeFailure(
                    code=RuntimeFailureCode.PROBE_EXIT,
                    message="OpenCode probe could not start",
                    details={"error": str(exc)},
                )
            ) from exc

        if result.returncode != 0:
            raise _ProbeCommandError(
                RuntimeFailure(
                    code=RuntimeFailureCode.PROBE_EXIT,
                    message="OpenCode probe exited unsuccessfully",
                    details={
                        "returncode": result.returncode,
                        "stderr": result.stderr.strip(),
                    },
                )
            )
        return "\n".join(
            part for part in (result.stdout, result.stderr) if part
        )
