"""Version-bound OpenCode runtime probe adapter."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from agenty.runtime.adapters import RuntimeAdapterError
from agenty.runtime.protocol import (
    AvailabilityEvent,
    CapabilityRecord,
    CapabilitySupport,
    ChannelMode,
    EvidenceLevel,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeIdentity,
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

    def _resolve_executable(self) -> str | None:
        candidate = Path(self.executable).expanduser()
        if candidate.parent != Path("."):
            return str(candidate.resolve()) if candidate.is_file() else None
        return shutil.which(self.executable)

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
