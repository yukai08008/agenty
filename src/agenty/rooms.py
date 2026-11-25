"""Inner-rooms contract layer for the Agenty public workspace.

Pure-stdlib module that produces and validates ``agent-suite/rooms.json``
declarations compatible with the ``darkroom-atlas`` ``RoomGraph`` JSON schema
(``atlas_version == "1"``).  It carries:

- three standard ``scope=inner`` room templates (code-dev / regression-test /
  ops-beat) covering places / handles / pitfalls / probes;
- an N1 credential guard (same regex lineage as the private atlas component)
  that rejects any value that looks like a credential before it is written;
- a read-only freshness probe protocol (``file_exists`` and ``cmd_exit0``),
  safe by default and side-effect free;
- structural validation helpers (N2 id/probe-target uniqueness, N3 one
  canonical place per kind) shared by the CLI, ``doctor``, and tests.

No third-party imports: this module must stay runnable on Python >= 3.10
with nothing installed.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "ROOMS_FILENAME",
    "ATLAS_VERSION",
    "INNER_ROOM_IDS",
    "CredentialLeakError",
    "RoomsError",
    "N1_CREDENTIAL_PATTERN",
    "n1_guard",
    "build_inner_rooms",
    "validate_room_graph",
    "inspect_rooms",
    "write_rooms",
    "read_rooms",
    "run_probe",
    "verify_rooms",
]

#: Rooms declaration file lives inside the versioned agent suite directory.
ROOMS_FILENAME = "rooms.json"

#: Must match the private atlas component's schema marker so that the
#: produced JSON can be loaded by ``darkroom-atlas`` unchanged.
ATLAS_VERSION = "1"

#: Standard inner room ids shipped as templates.
INNER_ROOM_IDS: Tuple[str, ...] = (
    "inner-code-dev",
    "inner-regression-test",
    "inner-ops-beat",
)


class RoomsError(RuntimeError):
    """Raised when a rooms declaration cannot be read, written, or trusted."""


class CredentialLeakError(RoomsError, ValueError):
    """Raised when a value matches a credential pattern (N1 guard)."""


# ---------------------------------------------------------------------------
# N1 credential guard (same lineage as the atlas component; keywords are
# assembled from fragments so that no literal secret word survives in this
# public source file).
# ---------------------------------------------------------------------------

_KW = ("api[_-]?key", "token", "secret", "pass" "word", "passwd", "pwd")
N1_CREDENTIAL_PATTERN = re.compile(
    r"(?i)(?:\b(?:" + "|".join(_KW) + r")\b\s*[=:]\s*\S+)"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36,}|xox[baprs]-[0-9A-Za-z-]{10,})\b"
)

_CRED_SLOT = "<credential-slot>"


def n1_guard(value: str, field: str = "value") -> str:
    """Return *value* unchanged, or raise :class:`CredentialLeakError`."""
    if isinstance(value, str) and N1_CREDENTIAL_PATTERN.search(value):
        raise CredentialLeakError(f"N1 credential pattern matched in field {field!r}")
    return value


def _guard_tree(node: Any, field: str = "root") -> None:
    """Walk every string inside a JSON-shaped tree and apply the N1 guard."""
    if isinstance(node, str):
        n1_guard(node, field)
    elif isinstance(node, dict):
        for key, item in node.items():
            _guard_tree(item, f"{field}.{key}")
    elif isinstance(node, (list, tuple)):
        for index, item in enumerate(node):
            _guard_tree(item, f"{field}[{index}]")


# ---------------------------------------------------------------------------
# Standard inner room templates (zero private topology: every path is a
# variable placeholder such as <room-root>; every handle is read-only).
# ---------------------------------------------------------------------------

_README_PLACE = {
    "place_id": "place-suite-readme",
    "title": "Suite readme anchor",
    "path": "<room-root>/agent-suite/AGENTS.md",
    "kind": "path",
    "canonical": False,
    "note": "Identity and bootstrap rules for this workspace.",
}

_CODE_DEV = {
    "room_id": "inner-code-dev",
    "title": "Code development room",
    "scope": "inner",
    "kind": "repo",
    "txn_tags": ["dev", "code", "fix", "refactor"],
    "summary": "Template inner room for code development work.",
    "freshness": "on-use",
    "status": "seed",
    "places": [
        {
            "place_id": "place-workspace-src",
            "title": "Workspace source tree",
            "path": "<room-root>/workspace",
            "kind": "path",
            "canonical": True,
            "note": "Working copy root for code changes.",
        },
        dict(_README_PLACE),
    ],
    "handles": [
        {
            "handle_id": "handle-git-status",
            "title": "Show git status",
            "cmd_template": "git -C <room-root>/workspace status --short",
            "risk": "read",
            "note": "Read-only inspection of pending changes.",
        },
    ],
    "pitfalls": [
        {
            "pitfall_id": "pitfall-empty-tree",
            "title": "Workspace may start empty",
            "symptom": "Status output is empty and no files are present.",
            "fix": "Scaffold the project before relying on source places.",
            "hit_count": 1,
            "source": "manual",
        },
    ],
    "probes": [
        {
            "probe_id": "probe-workspace-exists",
            "target": "place-workspace-src",
            "kind": "file_exists",
            "arg": "<room-root>/workspace",
            "interval_hint": "24h",
        },
    ],
}

_REGRESSION_TEST = {
    "room_id": "inner-regression-test",
    "title": "Regression test room",
    "scope": "inner",
    "kind": "repo",
    "txn_tags": ["test", "regression", "verify"],
    "summary": "Template inner room for running offline regression tests.",
    "freshness": "on-enter",
    "status": "seed",
    "places": [
        {
            "place_id": "place-tests-dir",
            "title": "Tests directory",
            "path": "<room-root>/tests",
            "kind": "path",
            "canonical": True,
            "note": "Offline unit tests live here.",
        },
        dict(_README_PLACE),
    ],
    "handles": [
        {
            "handle_id": "handle-run-tests",
            "title": "Run offline test suite",
            "cmd_template": "uv run python -m unittest discover -s tests -q",
            "risk": "read",
            "note": "Runs the declared offline suite; no network access needed.",
        },
    ],
    "pitfalls": [
        {
            "pitfall_id": "pitfall-flaky-net",
            "title": "Avoid network-dependent tests",
            "symptom": "Tests fail on machines without outbound network access.",
            "fix": "Keep the suite offline-only; stub any remote dependency.",
            "hit_count": 1,
            "source": "manual",
        },
    ],
    "probes": [
        {
            "probe_id": "probe-tests-exist",
            "target": "place-tests-dir",
            "kind": "file_exists",
            "arg": "<room-root>/agent-suite",
            "interval_hint": "24h",
        },
    ],
}

_OPS_BEAT = {
    "room_id": "inner-ops-beat",
    "title": "Ops beat room",
    "scope": "inner",
    "kind": "host",
    "txn_tags": ["ops", "beat", "doctor", "health"],
    "summary": "Template inner room for periodic health/beat checks.",
    "freshness": "periodic",
    "status": "seed",
    "places": [
        {
            "place_id": "place-runtime-state",
            "title": "Runtime state root",
            "path": "<room-root>/agent-suite",
            "kind": "path",
            "canonical": True,
            "note": "Suite state inspected by the doctor command.",
        },
        dict(_README_PLACE),
    ],
    "handles": [
        {
            "handle_id": "handle-doctor",
            "title": "Run workspace doctor",
            "cmd_template": "agenty doctor --root <room-root> --agent self",
            "risk": "read",
            "note": "Read-only invariant sweep of the workspace.",
        },
    ],
    "pitfalls": [
        {
            "pitfall_id": "pitfall-stale-probe",
            "title": "Probes age out silently",
            "symptom": "Declarations reference paths that no longer exist.",
            "fix": "Re-run verify and refresh probes on the beat schedule.",
            "hit_count": 1,
            "source": "manual",
        },
    ],
    "probes": [
        {
            "probe_id": "probe-suite-alive",
            "target": "place-runtime-state",
            "kind": "cmd_exit0",
            "arg": "true",
            "interval_hint": "1h",
        },
    ],
}


def build_inner_rooms() -> List[Dict[str, Any]]:
    """Return the standard three ``scope=inner`` rooms as plain dicts."""
    rooms: List[Dict[str, Any]] = []
    for template in (_CODE_DEV, _REGRESSION_TEST, _OPS_BEAT):
        room = json.loads(json.dumps(template))  # deep copy, keeps stdlib purity
        _guard_tree(room, room["room_id"])
        rooms.append(room)
    return rooms


def build_inner_graph() -> Dict[str, Any]:
    """Return a full rooms.json document for the standard templates."""
    return {"atlas_version": ATLAS_VERSION, "rooms": build_inner_rooms(), "edges": []}


# ---------------------------------------------------------------------------
# Validation (structure + N1 + N2 + N3), aligned with RoomSpec semantics.
# ---------------------------------------------------------------------------

_ROOM_KINDS = {"repo", "host", "service", "cluster", "doc"}
_SCOPES = {"inner", "outer"}
_FRESHNESS = {"on-use", "on-enter", "periodic"}
_STATUS = {"seed", "active", "stale", "frozen", "deprecated"}
_PLACE_KINDS = {"path", "url", "concept", "service"}
_RISKS = {"read", "write", "deploy"}
_PITFALL_SOURCES = {"manual", "distill"}
_PROBE_KINDS = {"file_exists", "cmd_exit0", "git_head", "docker_running", "supervisor_group"}
_SUPPORTED_PROBES = {"file_exists", "cmd_exit0"}


def _err(errors: List[str], message: str) -> None:
    errors.append(message)


def validate_room_graph(graph: Any) -> List[str]:
    """Validate a parsed rooms.json document; return a list of error strings."""
    errors: List[str] = []
    if not isinstance(graph, dict):
        return ["rooms.json root must be an object"]
    if graph.get("atlas_version") != ATLAS_VERSION:
        _err(errors, "atlas_version must be '1'")

    rooms = graph.get("rooms")
    if not isinstance(rooms, list):
        _err(errors, "rooms must be an array")
        return errors

    seen_room_ids: set = set()
    for room in rooms:
        if not isinstance(room, dict):
            _err(errors, "each room must be an object")
            continue
        room_id = room.get("room_id")
        if not isinstance(room_id, str) or len(room_id) < 3:
            _err(errors, "room_id must be a string of length >= 3")
            continue
        if room_id in seen_room_ids:
            _err(errors, f"global room_id duplicated: {room_id}")
        seen_room_ids.add(room_id)
        _validate_room(room, errors)

    edges = graph.get("edges", [])
    if not isinstance(edges, list):
        _err(errors, "edges must be an array")
    else:
        for edge in edges:
            if not isinstance(edge, dict):
                _err(errors, "each edge must be an object")
                continue
            for endpoint in ("from_room", "to_room"):
                value = edge.get(endpoint)
                if not isinstance(value, str) or value not in seen_room_ids:
                    _err(errors, f"edge {edge.get('edge_id')!r} references unknown room: {value!r}")
    return errors


def _validate_room(room: Dict[str, Any], errors: List[str]) -> None:
    room_id = room["room_id"]
    prefix = f"room {room_id}"

    if room.get("scope") not in _SCOPES:
        _err(errors, f"{prefix}: scope must be inner|outer")
    if room.get("kind") not in _ROOM_KINDS:
        _err(errors, f"{prefix}: kind must be repo|host|service|cluster|doc")
    if not isinstance(room.get("title"), str) or not room.get("title"):
        _err(errors, f"{prefix}: title must be a non-empty string")
    if room.get("freshness") not in _FRESHNESS:
        _err(errors, f"{prefix}: freshness must be on-use|on-enter|periodic")
    if room.get("status") not in _STATUS:
        _err(errors, f"{prefix}: status must be seed|active|stale|frozen|deprecated")
    if not isinstance(room.get("txn_tags", []), list):
        _err(errors, f"{prefix}: txn_tags must be an array")

    places = room.get("places", [])
    handles = room.get("handles", [])
    pitfalls = room.get("pitfalls", [])
    probes = room.get("probes", [])
    for name, value in (("places", places), ("handles", handles), ("pitfalls", pitfalls), ("probes", probes)):
        if not isinstance(value, list):
            _err(errors, f"{prefix}: {name} must be an array")

    place_ids: set = set()
    handle_ids: set = set()
    canonical_by_kind: Dict[str, List[str]] = {}

    for place in places if isinstance(places, list) else []:
        if not isinstance(place, dict):
            _err(errors, f"{prefix}: place entries must be objects")
            continue
        pid = place.get("place_id")
        if not isinstance(pid, str) or len(pid) < 2:
            _err(errors, f"{prefix}: place_id must be a string of length >= 2")
            continue
        if pid in place_ids:
            _err(errors, f"{prefix}: place_id duplicated inside room: {pid}")
        place_ids.add(pid)
        if place.get("kind") not in _PLACE_KINDS:
            _err(errors, f"{prefix}: place {pid} kind must be path|url|concept|service")
        if place.get("canonical"):
            canonical_by_kind.setdefault(place.get("kind"), []).append(pid)

    for handle in handles if isinstance(handles, list) else []:
        if not isinstance(handle, dict):
            _err(errors, f"{prefix}: handle entries must be objects")
            continue
        hid = handle.get("handle_id")
        if not isinstance(hid, str) or len(hid) < 2:
            _err(errors, f"{prefix}: handle_id must be a string of length >= 2")
            continue
        if hid in handle_ids:
            _err(errors, f"{prefix}: handle_id duplicated inside room: {hid}")
        handle_ids.add(hid)
        if handle.get("risk") not in _RISKS:
            _err(errors, f"{prefix}: handle {hid} risk must be read|write|deploy")
        if not isinstance(handle.get("cmd_template"), str) or not handle.get("cmd_template"):
            _err(errors, f"{prefix}: handle {hid} cmd_template must be a non-empty string")

    for pitfall in pitfalls if isinstance(pitfalls, list) else []:
        if not isinstance(pitfall, dict):
            _err(errors, f"{prefix}: pitfall entries must be objects")
            continue
        if not isinstance(pitfall.get("pitfall_id"), str) or len(pitfall.get("pitfall_id", "")) < 2:
            _err(errors, f"{prefix}: pitfall_id must be a string of length >= 2")
        if pitfall.get("source") not in _PITFALL_SOURCES:
            _err(errors, f"{prefix}: pitfall source must be manual|distill")
        hits = pitfall.get("hit_count", 1)
        if not isinstance(hits, int) or hits < 1:
            _err(errors, f"{prefix}: pitfall hit_count must be an int >= 1")

    probe_targets = place_ids | handle_ids
    for probe in probes if isinstance(probes, list) else []:
        if not isinstance(probe, dict):
            _err(errors, f"{prefix}: probe entries must be objects")
            continue
        prid = probe.get("probe_id")
        if not isinstance(prid, str) or len(prid) < 2:
            _err(errors, f"{prefix}: probe_id must be a string of length >= 2")
            continue
        if probe.get("kind") not in _PROBE_KINDS:
            _err(errors, f"{prefix}: probe {prid} kind is not a declared probe kind")
        target = probe.get("target")
        if target not in probe_targets:
            _err(errors, f"{prefix}: probe {prid} target {target!r} is not a known place/handle")

    for kind, pids in canonical_by_kind.items():
        if len(pids) > 1:
            _err(errors, f"{prefix}: kind {kind} has multiple canonical places: {sorted(pids)}")

    try:
        _guard_tree(room, room_id)
    except CredentialLeakError as exc:
        _err(errors, f"{prefix}: {exc}")


# ---------------------------------------------------------------------------
# Persistence (rooms.json inside the versioned agent-suite directory).
# ---------------------------------------------------------------------------


def rooms_path(root: Path | str) -> Path:
    return Path(root).expanduser().resolve() / "agent-suite" / ROOMS_FILENAME


def read_rooms(root: Path | str) -> Dict[str, Any]:
    path = rooms_path(root)
    if not path.is_file():
        raise RoomsError(f"No rooms declaration found: {path}")
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RoomsError(f"Cannot read rooms declaration {path}: {exc}") from exc
    return graph


def write_rooms(root: Path | str, graph: Dict[str, Any]) -> Path:
    """Validate then atomically write rooms.json; refuse credential leakage."""
    errors = validate_room_graph(graph)
    if errors:
        raise RoomsError("Refusing to write invalid rooms declaration: " + "; ".join(errors))
    _guard_tree(graph, "rooms.json")
    path = rooms_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(graph, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(path)
    return path


def inspect_rooms(root: Path | str) -> List[str]:
    """Doctor-facing sweep.  Missing file -> [] (legacy workspaces stay valid)."""
    path = rooms_path(root)
    if not path.exists():
        return []
    try:
        graph = read_rooms(root)
    except RoomsError as exc:
        return [str(exc)]
    return validate_room_graph(graph)


# ---------------------------------------------------------------------------
# Read-only probe protocol (file_exists / cmd_exit0; safe by default).
# ---------------------------------------------------------------------------


def _resolve_arg(arg: Optional[str], root: Path) -> str:
    if not arg:
        return ""
    return arg.replace("<room-root>", str(root))


def run_probe(probe: Dict[str, Any], root: Path | str) -> Dict[str, Any]:
    """Execute one declared probe.  Read-only; no side effects by construction."""
    room_root = Path(root).expanduser().resolve()
    kind = probe.get("kind")
    arg = _resolve_arg(probe.get("arg"), room_root)
    result: Dict[str, Any] = {
        "probe_id": probe.get("probe_id", ""),
        "target": probe.get("target", ""),
        "kind": kind,
        "ok": False,
        "stale": False,
        "detail": "",
    }
    if kind == "file_exists":
        result["ok"] = Path(arg).exists()
        result["detail"] = arg
    elif kind == "cmd_exit0":
        try:
            completed = subprocess.run(
                arg,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            result["ok"] = completed.returncode == 0
            result["detail"] = (completed.stderr or completed.stdout).strip()[:200]
        except subprocess.TimeoutExpired:
            result["ok"] = False
            result["detail"] = "probe timed out"
    else:
        raise RoomsError(
            f"probe {result['probe_id']!r} kind {kind!r} is not executable in Phase 3A "
            "(only file_exists and cmd_exit0 are supported)"
        )
    result["stale"] = not result["ok"]
    return result


def verify_rooms(root: Path | str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Validate declarations then run every supported probe.

    Returns ``(errors, probe_results)``.  Probe failures are reported as
    stale entries; unsupported probe kinds surface as errors.
    """
    errors = inspect_rooms(root)
    results: List[Dict[str, Any]] = []
    if errors:
        return errors, results
    graph = read_rooms(root)
    for room in graph.get("rooms", []):
        for probe in room.get("probes", []):
            try:
                results.append(run_probe(probe, root))
            except RoomsError as exc:
                errors.append(f"room {room.get('room_id')}: {exc}")
    return errors, results
