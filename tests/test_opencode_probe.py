import sys
from pathlib import Path

from agenty.runtime.machine import RuntimeProbeMachine
from agenty.runtime.opencode import OpenCodeRuntimeAdapter
from agenty.runtime.protocol import (
    AvailabilityState,
    CapabilitySupport,
    EvidenceLevel,
    RuntimeFailureCode,
)


HELP_TEXT = """Options:
  --model <model>
  --variant <effort>
  --session <id>
  --continue
  --fork
  --interactive
  --format json
  --file <path>
"""


def fake_opencode(
    tmp_path: Path,
    version: str = "1.18.26",
    version_exit: int = 0,
    help_exit: int = 0,
    help_to_stderr: bool = False,
    delay: float = 0,
):
    path = tmp_path / "opencode"
    log_path = tmp_path / "calls.log"
    path.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, sys, time\n"
        f"VERSION = {version!r}\n"
        f"HELP = {HELP_TEXT!r}\n"
        f"LOG = pathlib.Path({str(log_path)!r})\n"
        "with LOG.open('a') as stream:\n"
        "    stream.write(' '.join(sys.argv[1:]) + '\\n')\n"
        f"time.sleep({delay!r})\n"
        "if '--version' in sys.argv:\n"
        "    print(VERSION)\n"
        f"    raise SystemExit({version_exit})\n"
        f"print(HELP, file=sys.stderr if {help_to_stderr!r} else sys.stdout)\n"
        f"raise SystemExit({help_exit})\n"
    )
    path.chmod(0o755)
    return path, log_path


def test_probe_reports_version_and_advertised_capabilities_without_model(tmp_path):
    executable, log_path = fake_opencode(tmp_path)

    snapshot = RuntimeProbeMachine(
        OpenCodeRuntimeAdapter(str(executable))
    ).probe()

    assert snapshot.availability is AvailabilityState.AVAILABLE
    assert snapshot.runtime.runtime_kind == "opencode"
    assert snapshot.runtime.runtime_version == "1.18.26"
    assert snapshot.runtime.executable == str(executable.resolve())
    capabilities = {record.capability: record for record in snapshot.capabilities}
    assert capabilities["model.selection"].support is CapabilitySupport.UNKNOWN
    assert capabilities["model.selection"].evidence is EvidenceLevel.ADVERTISED
    assert capabilities["session.fork"].constraints == (
        "requires --continue or --session",
    )
    assert log_path.read_text().splitlines() == ["--version", "run --help"]


def test_missing_opencode_is_unavailable(tmp_path):
    snapshot = RuntimeProbeMachine(
        OpenCodeRuntimeAdapter(str(tmp_path / "missing"))
    ).probe()

    assert snapshot.availability is AvailabilityState.UNAVAILABLE
    assert snapshot.failure is not None
    assert snapshot.failure.code is RuntimeFailureCode.NOT_FOUND


def test_probe_accepts_successful_help_written_to_stderr(tmp_path):
    executable, _ = fake_opencode(tmp_path, help_to_stderr=True)

    snapshot = RuntimeProbeMachine(
        OpenCodeRuntimeAdapter(str(executable))
    ).probe()

    assert snapshot.availability is AvailabilityState.AVAILABLE
    assert any(
        record.capability == "session.resume_by_id"
        for record in snapshot.capabilities
    )


def test_invalid_version_is_incompatible(tmp_path):
    executable, _ = fake_opencode(tmp_path, version="development")

    snapshot = RuntimeProbeMachine(
        OpenCodeRuntimeAdapter(str(executable))
    ).probe()

    assert snapshot.availability is AvailabilityState.INCOMPATIBLE
    assert snapshot.failure is not None
    assert snapshot.failure.code is RuntimeFailureCode.INVALID_VERSION


def test_valid_but_unsupported_version_is_incompatible(tmp_path):
    executable, _ = fake_opencode(tmp_path, version="1.18.27")

    snapshot = RuntimeProbeMachine(
        OpenCodeRuntimeAdapter(str(executable))
    ).probe()

    assert snapshot.availability is AvailabilityState.INCOMPATIBLE
    assert snapshot.failure is not None
    assert snapshot.failure.code is RuntimeFailureCode.UNSUPPORTED_VERSION


def test_nonzero_version_probe_is_unavailable(tmp_path):
    executable, _ = fake_opencode(tmp_path, version_exit=9)

    snapshot = RuntimeProbeMachine(
        OpenCodeRuntimeAdapter(str(executable))
    ).probe()

    assert snapshot.availability is AvailabilityState.UNAVAILABLE
    assert snapshot.failure is not None
    assert snapshot.failure.code is RuntimeFailureCode.PROBE_EXIT


def test_probe_timeout_is_unavailable(tmp_path):
    executable, _ = fake_opencode(tmp_path, delay=1)

    snapshot = RuntimeProbeMachine(
        OpenCodeRuntimeAdapter(str(executable), timeout_seconds=0.01)
    ).probe()

    assert snapshot.availability is AvailabilityState.UNAVAILABLE
    assert snapshot.failure is not None
    assert snapshot.failure.code is RuntimeFailureCode.PROBE_TIMEOUT


def test_capability_probe_failure_is_degraded(tmp_path):
    executable, _ = fake_opencode(tmp_path, help_exit=9)

    snapshot = RuntimeProbeMachine(
        OpenCodeRuntimeAdapter(str(executable))
    ).probe()

    assert snapshot.availability is AvailabilityState.DEGRADED
    assert snapshot.runtime.runtime_version == "1.18.26"
    assert snapshot.failure is not None
    assert snapshot.failure.code is RuntimeFailureCode.PROBE_EXIT
