"""OpenCode implementation of the Runtime adapter probe contract."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from agenty.runtime.adapters import RuntimeAdapterError
from agenty.runtime.models import (
    RuntimeCapability,
    RuntimeFailure,
    RuntimeFailureCode,
    RuntimeInfo,
)


_VERSION = re.compile(r"\b\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?\b")


class OpenCodeRuntimeAdapter:
    def __init__(self, executable: str = "opencode", timeout_seconds: float = 5):
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    @property
    def runtime_id(self) -> str:
        return "opencode"

    def probe(self) -> RuntimeInfo:
        executable = self._resolve_executable()
        if executable is None:
            raise RuntimeAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.NOT_FOUND,
                    message=f"runtime executable not found: {self.executable}",
                )
            )

        version_output = self._run_probe(executable, "--version")
        match = _VERSION.search(version_output)
        if match is None:
            raise RuntimeAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.INVALID_VERSION,
                    message="OpenCode returned an unrecognized version",
                    details={"output": version_output.strip()},
                )
            )

        run_help = self._run_probe(executable, "run", "--help")
        capabilities = self._capabilities_from_help(run_help)
        return RuntimeInfo(
            runtime_id=self.runtime_id,
            kind="opencode",
            version=match.group(0),
            executable=executable,
            capabilities=frozenset(capabilities),
            evidence={
                "version": version_output.strip(),
                "capability_source": "opencode run --help",
            },
        )

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
            raise RuntimeAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.PROBE_TIMEOUT,
                    message="OpenCode probe timed out",
                    details={"timeout_seconds": self.timeout_seconds},
                )
            ) from exc
        except OSError as exc:
            raise RuntimeAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.PROBE_EXIT,
                    message="OpenCode probe could not start",
                    details={"error": str(exc)},
                )
            ) from exc

        if result.returncode != 0:
            raise RuntimeAdapterError(
                RuntimeFailure(
                    code=RuntimeFailureCode.PROBE_EXIT,
                    message="OpenCode probe exited unsuccessfully",
                    details={
                        "returncode": result.returncode,
                        "stderr": result.stderr.strip(),
                    },
                )
            )
        # OpenCode 1.18.x writes command help to stderr even with exit code 0.
        # Both streams are therefore evidence; neither is treated as failure by
        # itself when the process succeeded.
        return "\n".join(part for part in (result.stdout, result.stderr) if part)

    @staticmethod
    def _capabilities_from_help(help_text: str) -> set[RuntimeCapability]:
        option_capabilities = {
            "--model": RuntimeCapability.MODELS,
            "--variant": RuntimeCapability.EFFORT_LEVELS,
            "--session": RuntimeCapability.SESSIONS,
            "--continue": RuntimeCapability.RESUME,
            "--fork": RuntimeCapability.FORK,
            "--interactive": RuntimeCapability.INTERACTIVE_WINDOW,
            "--format": RuntimeCapability.STRUCTURED_OUTPUT,
            "--file": RuntimeCapability.ATTACHMENTS,
        }
        return {
            capability
            for option, capability in option_capabilities.items()
            if option in help_text
        }
