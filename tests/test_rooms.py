"""Phase 3A inner-rooms contract tests.

Covers: template generation, N1 credential guard, read-only probes,
workspace/CLI integration, doctor sweep, the public-repo desensitization
gate (D16), and the RoomGraph JSON schema contract snapshot shared with
the private atlas component (atlas_version "1").
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"

from agenty.rooms import (  # noqa: E402
    ATLAS_VERSION,
    CredentialLeakError,
    INNER_ROOM_IDS,
    ROOMS_FILENAME,
    RoomsError,
    build_inner_graph,
    build_inner_rooms,
    inspect_rooms,
    n1_guard,
    read_rooms,
    rooms_path,
    run_probe,
    validate_room_graph,
    verify_rooms,
    write_rooms,
)


def _write_graph(root: Path, graph) -> Path:
    return write_rooms(root, graph)


class TemplateTests(unittest.TestCase):
    def test_templates_cover_all_contract_fields(self):
        """Every template room carries the full RoomSpec field set."""
        expected_keys = {
            "room_id",
            "title",
            "scope",
            "kind",
            "txn_tags",
            "summary",
            "freshness",
            "status",
            "places",
            "handles",
            "pitfalls",
            "probes",
        }
        rooms = build_inner_rooms()
        self.assertEqual([r["room_id"] for r in rooms], list(INNER_ROOM_IDS))
        for room in rooms:
            self.assertTrue(expected_keys.issubset(room.keys()), room["room_id"])
            self.assertEqual(room["scope"], "inner")
            for place in room["places"]:
                self.assertTrue({"place_id", "title", "kind", "canonical"}.issubset(place.keys()))
            for handle in room["handles"]:
                self.assertTrue({"handle_id", "title", "cmd_template", "risk"}.issubset(handle.keys()))
                self.assertEqual(handle["risk"], "read")
            for pitfall in room["pitfalls"]:
                self.assertTrue({"pitfall_id", "title", "symptom", "fix", "source"}.issubset(pitfall.keys()))
            for probe in room["probes"]:
                self.assertTrue({"probe_id", "target", "kind"}.issubset(probe.keys()))
                self.assertIn(probe["kind"], {"file_exists", "cmd_exit0"})

    def test_templates_have_unique_canonical_per_kind(self):
        """N3: exactly one canonical place per kind inside every template room."""
        for room in build_inner_rooms():
            by_kind = {}
            for place in room["places"]:
                if place.get("canonical"):
                    by_kind.setdefault(place["kind"], []).append(place["place_id"])
            for kind, pids in by_kind.items():
                self.assertEqual(len(pids), 1, f"{room['room_id']} kind={kind}: {pids}")

    def test_validate_accepts_builtin_graph(self):
        self.assertEqual(validate_room_graph(build_inner_graph()), [])

    def test_validate_rejects_duplicate_place_and_bad_probe_target(self):
        graph = build_inner_graph()
        room = graph["rooms"][0]
        room["places"].append(dict(room["places"][0]))  # duplicate place_id
        room["probes"].append(
            {"probe_id": "probe-bad", "target": "no-such-target", "kind": "file_exists"}
        )
        errors = validate_room_graph(graph)
        self.assertTrue(any("duplicated" in e for e in errors))
        self.assertTrue(any("not a known place/handle" in e for e in errors))

    def test_validate_rejects_unknown_edge_room(self):
        graph = build_inner_graph()
        graph["edges"].append({"edge_id": "e1", "from_room": "inner-code-dev", "to_room": "ghost-room"})
        errors = validate_room_graph(graph)
        self.assertTrue(any("unknown room" in e for e in errors))


class N1GuardTests(unittest.TestCase):
    def test_guard_blocks_credential_assignment(self):
        with self.assertRaises(CredentialLeakError):
            n1_guard("export API_KEY=abcd1234")

    def test_guard_blocks_token_and_pem_shapes(self):
        with self.assertRaises(CredentialLeakError):
            n1_guard("ghp_" + "a" * 36)
        with self.assertRaises(CredentialLeakError):
            n1_guard("-----BEGIN " + "RSA PRIVATE" + " KEY-----")

    def test_guard_passes_plain_values(self):
        self.assertEqual(n1_guard("plain value", "field"), "plain value")

    def test_write_rooms_rejects_credential_leak(self):
        graph = build_inner_graph()
        graph["rooms"][0]["summary"] = "deploy with API_KEY=hunter2"
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(RoomsError):
                write_rooms(Path(td), graph)
            self.assertFalse(rooms_path(td).exists())


class ProbeTests(unittest.TestCase):
    def test_file_exists_probe_pass_and_stale(self):
        probe = {"probe_id": "p1", "target": "t", "kind": "file_exists"}
        with tempfile.TemporaryDirectory() as td:
            probe["arg"] = str(Path(td) / "absent.txt")
            stale = run_probe(probe, td)
            self.assertFalse(stale["ok"])
            self.assertTrue(stale["stale"])
            (Path(td) / "absent.txt").write_text("x", encoding="utf-8")
            ok = run_probe(probe, td)
            self.assertTrue(ok["ok"])
            self.assertFalse(ok["stale"])

    def test_file_exists_probe_resolves_room_root_placeholder(self):
        probe = {"probe_id": "p2", "target": "t", "kind": "file_exists", "arg": "<room-root>/tests"}
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "tests").mkdir()
            self.assertTrue(run_probe(probe, td)["ok"])

    def test_cmd_exit0_probe(self):
        probe = {"probe_id": "p3", "target": "t", "kind": "cmd_exit0", "arg": "true"}
        self.assertTrue(run_probe(probe, "/tmp")["ok"])
        probe["arg"] = "false"
        self.assertFalse(run_probe(probe, "/tmp")["ok"])

    def test_unsupported_probe_kind_is_rejected(self):
        probe = {"probe_id": "p4", "target": "t", "kind": "docker_running"}
        with self.assertRaises(RoomsError):
            run_probe(probe, "/tmp")

    def test_verify_reports_stale_probes(self):
        graph = build_inner_graph()
        graph["rooms"][0]["places"][0]["path"] = "<room-root>/workspace"
        graph["rooms"][0]["probes"][0]["arg"] = "<room-root>/definitely-missing"
        with tempfile.TemporaryDirectory() as td:
            write_rooms(Path(td), graph)
            errors, probes = verify_rooms(td)
            self.assertEqual(errors, [])
            self.assertTrue(probes[0]["stale"])


class WorkspaceIntegrationTests(unittest.TestCase):
    def _env(self, root: Path) -> dict:
        env = os.environ.copy()
        env["AGENTY_HOME"] = str(root / "home")
        env["AGENTY_AGENTS_HOME"] = str(root / "workers")
        return env

    def _prepare(self, env) -> None:
        run = lambda *argv: subprocess.run(  # noqa: E731
            [sys.executable, "-m", "agenty.cli", *argv],
            env=env,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(run("init").returncode, 0)
        self.assertEqual(run("runtime", "add", "mock", sys.executable, "-c", "pass").returncode, 0)
        self.assertEqual(run("claim", "rooms-agent", "--runtime", "mock").returncode, 0)

    def test_workspace_create_writes_rooms_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._prepare(self._env(root))
            workers = root / "workers" / "rooms-agent"
            result = subprocess.run(
                [sys.executable, "-m", "agenty.cli", "workspace", "create", "rooms-agent"],
                env=self._env(root),
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            declared = workers / "agent-suite" / ROOMS_FILENAME
            self.assertTrue(declared.is_file())
            self.assertEqual(validate_room_graph(json.loads(declared.read_text(encoding="utf-8"))), [])

    def test_workspace_create_opt_out(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._prepare(self._env(root))
            env = self._env(root)
            from agenty.store import AgentyStore
            from agenty.workspace import create_worker

            store = AgentyStore(home=env["AGENTY_HOME"], agents_home=env["AGENTY_AGENTS_HOME"])
            agent = store.resolve_agent("rooms-agent")
            target = root / "optout"
            record = create_worker(store, agent.agent_id, path=str(target), with_rooms=False)
            self.assertFalse((Path(record.bindings["active_root"]) / "agent-suite" / ROOMS_FILENAME).exists())

    def test_inspect_rooms_missing_file_is_silent(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(inspect_rooms(td), [])


class CliRoomsTests(unittest.TestCase):
    def _env(self, root: Path) -> dict:
        env = os.environ.copy()
        env["AGENTY_HOME"] = str(root / "home")
        env["AGENTY_AGENTS_HOME"] = str(root / "workers")
        return env

    def _run(self, env, *argv):
        return subprocess.run(
            [sys.executable, "-m", "agenty.cli", *argv],
            env=env,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )

    def test_rooms_list_and_verify_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env = self._env(root)
            self.assertEqual(self._run(env, "init").returncode, 0)
            self.assertEqual(
                self._run(env, "runtime", "add", "mock", sys.executable, "-c", "pass").returncode, 0
            )
            self.assertEqual(self._run(env, "claim", "rooms-cli", "--runtime", "mock").returncode, 0)
            self.assertEqual(self._run(env, "workspace", "create", "rooms-cli").returncode, 0)

            listed = self._run(env, "rooms", "list", "--agent", "rooms-cli", "--json")
            self.assertEqual(listed.returncode, 0, listed.stderr)
            graph = json.loads(listed.stdout)
            self.assertEqual(graph["atlas_version"], ATLAS_VERSION)
            self.assertEqual(len(graph["rooms"]), 3)

            verified = self._run(env, "rooms", "verify", "--agent", "rooms-cli", "--json")
            self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
            payload = json.loads(verified.stdout)
            self.assertEqual(payload["errors"], [])
            self.assertGreaterEqual(len(payload["probes"]), 3)

    def test_rooms_verify_exit6_on_stale(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env = self._env(root)
            self.assertEqual(self._run(env, "init").returncode, 0)
            self.assertEqual(self._run(env, "rooms", "init", "--root", str(root / "ws")).returncode, 0)
            graph = read_rooms(root / "ws")
            graph["rooms"][0]["probes"][0]["arg"] = "<room-root>/gone"
            write_rooms(root / "ws", graph)
            verified = self._run(env, "rooms", "verify", "--root", str(root / "ws"), "--json")
            self.assertEqual(verified.returncode, 6)
            self.assertTrue(json.loads(verified.stdout)["stale_count"] >= 1)

    def test_doctor_sweep_includes_rooms(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env = self._env(root)
            self.assertEqual(self._run(env, "init").returncode, 0)
            self.assertEqual(
                self._run(env, "runtime", "add", "mock", sys.executable, "-c", "pass").returncode, 0
            )
            self.assertEqual(self._run(env, "claim", "doc-agent", "--runtime", "mock").returncode, 0)
            self.assertEqual(self._run(env, "workspace", "create", "doc-agent").returncode, 0)
            # Corrupt the declaration so the doctor sweep must flag it.
            declared = root / "workers" / "doc-agent" / "agent-suite" / ROOMS_FILENAME
            corrupt = json.loads(declared.read_text(encoding="utf-8"))
            corrupt["atlas_version"] = "999"
            declared.write_text(json.dumps(corrupt), encoding="utf-8")
            doctor = self._run(env, "doctor", "doc-agent")
            self.assertEqual(doctor.returncode, 1)
            self.assertIn("atlas_version", doctor.stdout + doctor.stderr)


class ContractSnapshotTests(unittest.TestCase):
    """RoomGraph JSON schema contract snapshot (atlas_version "1")."""

    def test_graph_shape_matches_atlas_contract(self):
        graph = build_inner_graph()
        self.assertEqual(
            set(graph.keys()), {"atlas_version", "rooms", "edges"}
        )
        self.assertEqual(graph["atlas_version"], "1")
        room = graph["rooms"][0]
        place = room["places"][0]
        handle = room["handles"][0]
        pitfall = room["pitfalls"][0]
        probe = room["probes"][0]
        # Field-name level alignment with PlaceNode/HandleAction/PitfallNote/VerifyProbe.
        self.assertTrue(set(place) <= {"place_id", "title", "path", "kind", "canonical", "note"})
        self.assertTrue(set(handle) <= {"handle_id", "title", "cmd_template", "risk", "note"})
        self.assertTrue(
            set(pitfall) <= {"pitfall_id", "title", "symptom", "fix", "hit_count", "source"}
        )
        self.assertTrue(set(probe) <= {"probe_id", "target", "kind", "arg", "interval_hint"})
        self.assertIn(room["kind"], {"repo", "host", "service", "cluster", "doc"})
        self.assertIn(room["freshness"], {"on-use", "on-enter", "periodic"})
        self.assertIn(room["status"], {"seed", "active", "stale", "frozen", "deprecated"})
        self.assertIn(place["kind"], {"path", "url", "concept", "service"})

    def test_rooms_json_not_gitignored(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8") if (REPO_ROOT / ".gitignore").exists() else ""
        self.assertNotIn(ROOMS_FILENAME, gitignore)


class D16DesensitizationTests(unittest.TestCase):
    """Public-repo purity gate: no hosts, LAN IPs, home dirs, internal
    domains, real-name-style identifiers, or credentials anywhere in the
    Phase 3A source and test surface."""

    PATTERNS = (
        (r"\b(?:10|172|192)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "LAN IP"),
        (r"/(?:root|home|Users)/[A-Za-z0-9_.-]+", "home directory"),
        (r"\b[a-z0-9-]+\.(?:" + "orb" + "itx" + "|internal|corp|local)\\b", "internal domain"),
        (r"gh[pousr]_[A-Za-z0-9]{20,}", "token shape"),
        (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "PEM key"),
    )

    def test_public_surface_is_desensitized(self):
        targets = [REPO_ROOT / "src" / "agenty" / "rooms.py", Path(__file__)]
        for target in targets:
            text = target.read_text(encoding="utf-8")
            for pattern, label in self.PATTERNS:
                hits = re.findall(pattern, text)
                self.assertEqual(
                    hits, [], f"{target.name}: {label} leaked: {hits[:3]}"
                )

    def test_rooms_module_is_stdlib_only(self):
        text = (REPO_ROOT / "src" / "agenty" / "rooms.py").read_text(encoding="utf-8")
        for banned in ("pydantic", "rich", "darkroom_atlas", "andy_app_components"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
