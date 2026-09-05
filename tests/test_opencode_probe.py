import sys
from pathlib import Path

from agenty.runtime.machine import RuntimeMachine
from agenty.runtime.models import (
    RuntimeCapability,
    RuntimeFailureCode,
    RuntimeState,
)
from agenty.runtime.opencode import OpenCodeRuntimeAdapter


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
    exit_code: int = 0,
    help_to_stderr: bool = False,
    delay: float = 0,
):
    path = tmp_path / "opencode"
    path.write_text(
        f"#!{sys.executable}\n"
        "import sys, time\n"
        f"VERSION = {version!r}\n"
        f"HELP = {HELP_TEXT!r}\n"
        f"time.sleep({delay!r})\n"
        f"HELP_TO_STDERR = {help_to_stderr!r}\n"
        "if '--version' in sys.argv:\n"
        "    print(VERSION)\n"
        "else:\n"
        "    print(HELP, file=sys.stderr if HELP_TO_STDERR else sys.stdout)\n"
        f"raise SystemExit({exit_code})\n"
    )
    path.chmod(0o755)
    return path


def test_probe_reads_version_and_capabilities_without_running_a_model(tmp_path):
    adapter = OpenCodeRuntimeAdapter(str(fake_opencode(tmp_path)))

    snapshot = RuntimeMachine(adapter).probe()

    assert snapshot.state == RuntimeState.READY
    assert snapshot.info is not None
    assert snapshot.info.version == "1.18.26"
    assert RuntimeCapability.MODELS in snapshot.info.capabilities
    assert RuntimeCapability.EFFORT_LEVELS in snapshot.info.capabilities
    assert RuntimeCapability.SESSIONS in snapshot.info.capabilities
    assert RuntimeCapability.STRUCTURED_OUTPUT in snapshot.info.capabilities
    assert snapshot.info.evidence["capability_source"] == "opencode run --help"


def test_missing_opencode_is_unavailable(tmp_path):
    adapter = OpenCodeRuntimeAdapter(str(tmp_path / "missing"))

    snapshot = RuntimeMachine(adapter).probe()

    assert snapshot.state == RuntimeState.UNAVAILABLE
    assert snapshot.failure is not None
    assert snapshot.failure.code == RuntimeFailureCode.NOT_FOUND


def test_probe_accepts_successful_help_written_to_stderr(tmp_path):
    adapter = OpenCodeRuntimeAdapter(
        str(fake_opencode(tmp_path, help_to_stderr=True))
    )

    snapshot = RuntimeMachine(adapter).probe()

    assert snapshot.info is not None
    assert RuntimeCapability.SESSIONS in snapshot.info.capabilities


def test_invalid_version_is_unavailable(tmp_path):
    adapter = OpenCodeRuntimeAdapter(str(fake_opencode(tmp_path, "development")))

    snapshot = RuntimeMachine(adapter).probe()

    assert snapshot.state == RuntimeState.UNAVAILABLE
    assert snapshot.failure is not None
    assert snapshot.failure.code == RuntimeFailureCode.INVALID_VERSION


def test_nonzero_probe_exit_is_unavailable(tmp_path):
    adapter = OpenCodeRuntimeAdapter(str(fake_opencode(tmp_path, exit_code=9)))

    snapshot = RuntimeMachine(adapter).probe()

    assert snapshot.state == RuntimeState.UNAVAILABLE
    assert snapshot.failure is not None
    assert snapshot.failure.code == RuntimeFailureCode.PROBE_EXIT


def test_probe_timeout_is_unavailable(tmp_path):
    adapter = OpenCodeRuntimeAdapter(
        str(fake_opencode(tmp_path, delay=1)), timeout_seconds=0.01
    )

    snapshot = RuntimeMachine(adapter).probe()

    assert snapshot.state == RuntimeState.UNAVAILABLE
    assert snapshot.failure is not None
    assert snapshot.failure.code == RuntimeFailureCode.PROBE_TIMEOUT


def test_public_runtime_models_have_no_vendor_specific_fields():
    from agenty.runtime import models

    public_models = [
        models.RuntimeFailure,
        models.RuntimeInfo,
        models.RuntimeEvent,
        models.RuntimeSnapshot,
    ]
    field_names = {
        name.lower()
        for model in public_models
        for name in model.__dataclass_fields__
    }

    assert not field_names & {"opencode", "codex", "claude", "variant"}
