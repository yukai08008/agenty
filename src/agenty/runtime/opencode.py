"""Version-bound OpenCode runtime probe adapter."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import signal
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

from agenty.runtime.adapters import (
    RuntimeAdapterError,
    RuntimeModelAdapterError,
    RuntimeTurnAdapterError,
    RuntimeTurnControl,
)
from agenty.runtime.opencode_events import OpenCodeEventNormalizer
from agenty.runtime.opencode_models import (
    InvalidOpenCodeModelCatalog,
    OpenCodeModelCatalogParser,
)
from agenty.runtime.protocol import (
    INTERACTION_APPROVAL_CAPABILITY,
    INTERACTION_AUTO_APPROVE_CAPABILITY,
    TURN_CANCEL_CAPABILITY,
    AvailabilityEvent,
    CapabilityRecord,
    CapabilitySupport,
    ChannelMode,
    EvidenceLevel,
    InteractionPolicyMode,
    RuntimeApprovalDecision,
    RuntimeEvent,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
    RuntimeModelCatalog,
    RuntimeTurnRequest,
    TurnEvent,
)

_VERSION = re.compile(r"\b\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?\b")
_SUPPORTED_VERSIONS = frozenset({"1.18.26"})
_CONFIG_CONTENT_ENV = "OPENCODE_CONFIG_CONTENT"
_DENY_AGENT = "agenty-deny-by-default"

_OPTION_CAPABILITIES = {
    "--model": "model.selection",
    "--variant": "effort.selection",
    "--session": "session.resume_by_id",
    "--continue": "session.resume_latest",
    "--fork": "session.fork",
    "--interactive": "channel.interactive_window",
    "--format": "output.structured",
    "--file": "input.attachments",
    "--auto": "interaction.auto_approve",
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
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.supported_versions = supported_versions or _SUPPORTED_VERSIONS
        self.event_normalizer = OpenCodeEventNormalizer()
        self.model_catalog_parser = OpenCodeModelCatalogParser()

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
            support = CapabilitySupport.UNKNOWN
            evidence = EvidenceLevel.ADVERTISED
            evidence_source = "opencode run --help"
            if capability == INTERACTION_AUTO_APPROVE_CAPABILITY:
                support = CapabilitySupport.SUPPORTED
                evidence = EvidenceLevel.INTEGRATION_VERIFIED
                evidence_source = "OpenCode 1.18.26 adapter integration"
            records.append(
                CapabilityRecord(
                    capability=capability,
                    runtime=runtime,
                    support=support,
                    evidence=evidence,
                    evidence_source=evidence_source,
                    constraints=constraints,
                )
            )
        records.extend(
            (
                CapabilityRecord(
                    capability=INTERACTION_APPROVAL_CAPABILITY,
                    runtime=runtime,
                    support=CapabilitySupport.UNSUPPORTED,
                    evidence=EvidenceLevel.INTEGRATION_VERIFIED,
                    evidence_source="OpenCode 1.18.26 transient JSON integration",
                    constraints=("no approval reply control plane",),
                ),
                CapabilityRecord(
                    capability=TURN_CANCEL_CAPABILITY,
                    runtime=runtime,
                    support=CapabilitySupport.SUPPORTED,
                    evidence=EvidenceLevel.INTEGRATION_VERIFIED,
                    evidence_source="OpenCode 1.18.26 adapter process control",
                ),
            )
        )
        return tuple(records)

    def probe_model_catalog(
        self,
        runtime: RuntimeIdentity,
    ) -> RuntimeModelCatalog:
        if (
            runtime.runtime_kind != "opencode"
            or runtime.runtime_version not in self.supported_versions
            or runtime.executable is None
        ):
            raise RuntimeModelAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.IDENTITY_MISMATCH,
                    message="model probe requires detected OpenCode identity",
                )
            )
        try:
            output = self._run_probe(
                runtime.executable,
                "models",
                "--verbose",
            )
            return self.model_catalog_parser.parse(output, runtime)
        except _ProbeCommandError as exc:
            raise RuntimeModelAdapterError(exc.failure) from exc
        except InvalidOpenCodeModelCatalog as exc:
            raise RuntimeModelAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.MODEL_CATALOG_INVALID,
                    message="OpenCode returned an invalid model catalog",
                    details={"error": str(exc)},
                )
            ) from exc

    def iter_turn_events(
        self,
        runtime: RuntimeIdentity,
        request: RuntimeTurnRequest,
        control: RuntimeTurnControl,
    ) -> Iterator[RuntimeEvent]:
        self._validate_turn(runtime, request)
        command = self._turn_command(runtime, request)
        environment = self._turn_environment(runtime, request, control)
        try:
            process = subprocess.Popen(
                command,
                cwd=request.working_directory,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                env=environment,
            )
        except OSError as exc:
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode turn could not start",
                    details={"error": str(exc)},
                )
            ) from exc

        try:
            yield self._turn_event(TurnEvent.TURN_ACCEPTED, runtime, request)

            stdout, stderr = self._wait_for_process(process, control)

            session_id = (
                request.session.session_id if request.session is not None else None
            )
            saw_event = False
            runtime_error = None
            for line_number, line in enumerate(stdout.splitlines(), start=1):
                if not line.strip():
                    continue
                normalized = self.event_normalizer.normalize_json_line(
                    line,
                    runtime,
                    request,
                    line_number=line_number,
                )
                raw = normalized.raw_event
                assert isinstance(raw, dict)
                saw_event = True
                event_session = normalized.session_id
                if event_session:
                    if session_id is not None and event_session != session_id:
                        raise self.event_normalizer.invalid_output(
                            "OpenCode changed sessionID during one turn",
                            raw_event=raw,
                            line_number=line_number,
                        )
                    session_id = event_session

                usage = self.event_normalizer.usage_event(
                    raw,
                    runtime,
                    request,
                    line_number=line_number,
                )
                yield normalized
                if usage is not None:
                    yield usage
                if raw.get("type") == "error":
                    runtime_error = raw

            if not saw_event or session_id is None:
                raise self.event_normalizer.invalid_output(
                    "OpenCode turn produced no session-bound JSON events"
                )
            if runtime_error is not None:
                raise RuntimeTurnAdapterError(
                    RuntimeFailure(
                        code=RuntimeFailureCode.TURN_FAILED,
                        message="OpenCode reported a runtime error",
                        details=self.event_normalizer.error_details(runtime_error),
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
        finally:
            if process.poll() is None:
                self._terminate_process(process)

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
        if request.session is not None and request.session.runtime != runtime:
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.SESSION_ID_MISMATCH,
                    message="session binding belongs to another runtime",
                    details={"session_id": request.session.session_id},
                )
            )
        if request.model is not None and request.model.runtime != runtime:
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.IDENTITY_MISMATCH,
                    message="model binding belongs to another runtime",
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
            selection = request.model.selection
            command.extend(("--model", selection.model.qualified_id))
            if selection.effort is not None:
                command.extend(("--variant", selection.effort))
        if request.session is not None:
            command.extend(("--session", request.session.session_id))
        if request.interaction.mode is InteractionPolicyMode.AUTO_APPROVE:
            command.append("--auto")
        else:
            command.extend(("--pure", "--agent", _DENY_AGENT))
        command.extend(("--", request.prompt))
        return command

    def _turn_environment(
        self,
        runtime: RuntimeIdentity,
        request: RuntimeTurnRequest,
        control: RuntimeTurnControl,
    ) -> dict[str, str]:
        environment = os.environ.copy()
        if request.interaction.mode is InteractionPolicyMode.AUTO_APPROVE:
            return environment
        environment.update(
            {
                "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
                "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1",
                "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
            }
        )
        raw_config = environment.get(_CONFIG_CONTENT_ENV)
        try:
            config = json.loads(raw_config) if raw_config else {}
        except json.JSONDecodeError as exc:
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode inline configuration is not valid JSON",
                )
            ) from exc
        if not isinstance(config, dict):
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode inline configuration must be a JSON object",
                )
            )
        agents = config.get("agent", {})
        if not isinstance(agents, dict):
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode inline agent configuration must be an object",
                )
            )
        mcp = config.get("mcp", {})
        if not isinstance(mcp, dict):
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode inline MCP configuration must be an object",
                )
            )
        disabled_mcp = dict(mcp)
        resolved = self._resolved_config(runtime, request, environment, control)
        resolved_mcp = resolved.get("mcp", {})
        if not isinstance(resolved_mcp, dict):
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode resolved MCP configuration was invalid",
                )
            )
        for name in resolved_mcp:
            entry = disabled_mcp.get(name, {})
            if not isinstance(entry, dict):
                entry = {}
            disabled_mcp[name] = {**entry, "enabled": False}
        config = dict(config)
        config["mcp"] = disabled_mcp
        config["agent"] = {
            **agents,
            _DENY_AGENT: {
                "description": "Agenty deny-by-default runtime agent",
                "mode": "primary",
                "permission": "deny",
            },
        }
        environment[_CONFIG_CONTENT_ENV] = json.dumps(
            config,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        self._validate_safe_config(
            self._resolved_config(runtime, request, environment, control)
        )
        return environment

    def _resolved_config(
        self,
        runtime: RuntimeIdentity,
        request: RuntimeTurnRequest,
        environment: dict[str, str],
        control: RuntimeTurnControl,
    ) -> dict[str, object]:
        assert runtime.executable is not None
        try:
            process = subprocess.Popen(
                [runtime.executable, "debug", "config", "--pure"],
                cwd=request.working_directory,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
        except OSError as exc:
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode safe configuration could not be resolved",
                )
            ) from exc
        stdout, _ = self._wait_for_process(
            process,
            control,
            timeout_seconds=min(self.timeout_seconds, 30),
            timeout_message="OpenCode safe configuration probe timed out",
        )
        if process.returncode != 0:
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode safe configuration was rejected",
                )
            )
        try:
            resolved = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode safe configuration was not JSON",
                )
            ) from exc
        if not isinstance(resolved, dict):
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode resolved configuration must be an object",
                )
            )
        return resolved

    @staticmethod
    def _validate_safe_config(config: dict[str, object]) -> None:
        agents = config.get("agent", {})
        selected = agents.get(_DENY_AGENT) if isinstance(agents, dict) else None
        permission = selected.get("permission") if isinstance(selected, dict) else None
        if permission not in ("deny", {"*": "deny"}):
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode deny agent was overridden by ambient configuration",
                )
            )
        mcp = config.get("mcp", {})
        if not isinstance(mcp, dict) or any(
            not isinstance(entry, dict) or entry.get("enabled") is not False
            for entry in mcp.values()
        ):
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.TURN_REJECTED,
                    message="OpenCode MCP configuration could not be disabled",
                )
            )

    def _wait_for_process(
        self,
        process: subprocess.Popen[str],
        control: RuntimeTurnControl,
        *,
        timeout_seconds: float | None = None,
        timeout_message: str = "OpenCode turn timed out",
    ) -> tuple[str, str]:
        timeout_seconds = timeout_seconds or self.timeout_seconds
        deadline = time.monotonic() + timeout_seconds
        try:
            while True:
                if control.cancelled:
                    _, stderr = self._terminate_process(process)
                    raise RuntimeTurnAdapterError(
                        RuntimeFailure(
                            code=RuntimeFailureCode.TURN_FAILED,
                            message="OpenCode turn was cancelled",
                            details={"actor": control.actor},
                        ),
                        cancelled=True,
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _, stderr = self._terminate_process(process)
                    raise RuntimeTurnAdapterError(
                        RuntimeFailure(
                            code=RuntimeFailureCode.TURN_TIMEOUT,
                            message=timeout_message,
                            details={
                                "timeout_seconds": timeout_seconds,
                                "stderr": stderr.strip(),
                            },
                        ),
                        timed_out=True,
                    )
                try:
                    return process.communicate(timeout=min(0.05, remaining))
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            if process.poll() is None:
                self._terminate_process(process)
            raise

    def reply_approval(self, decision: RuntimeApprovalDecision) -> None:
        raise RuntimeTurnAdapterError(
            RuntimeFailure(
                code=RuntimeFailureCode.INTERACTION_UNSUPPORTED,
                message="OpenCode transient process cannot receive approval replies",
                details={"request_id": decision.request_id},
            )
        )

    def _terminate_process(
        self,
        process: subprocess.Popen[str],
    ) -> tuple[str, str]:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            return process.communicate(timeout=1)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeTurnAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.INTERNAL,
                    message="OpenCode process could not be reaped",
                    details={"process_id": process.pid},
                )
            ) from exc

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
