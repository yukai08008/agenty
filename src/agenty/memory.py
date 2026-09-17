"""Explicit, auditable memory write-back for resolved Agent layers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agenty.harness import ResolvedContext


class MemoryWriteError(ValueError):
    """A requested memory write violates the resolved layer boundary."""


class MemoryWriteAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    executor_agent_id: str
    target_layer: str
    memory_path: str
    previous_sha256: str
    resulting_sha256: str
    changed_fields: list[str] = Field(default_factory=list)
    conflicting_fields: list[str] = Field(default_factory=list)


def write_memory(
    context: ResolvedContext,
    *,
    target_layer: str | Path,
    updates: dict[str, Any],
    audit_directory: str | Path,
) -> MemoryWriteAudit:
    """Write MEMORY.json only to one layer frozen in the context manifest."""
    target = Path(target_layer).expanduser().resolve()
    allowed = {Path(layer).resolve() for layer in context.manifest.loaded_layers}
    if target not in allowed:
        raise MemoryWriteError("memory target is not a loaded context layer")
    if not isinstance(updates, dict) or not updates:
        raise MemoryWriteError("memory updates must be a non-empty object")
    memory_path = target / "MEMORY.json"
    if not memory_path.is_file():
        raise MemoryWriteError("target layer has no MEMORY.json")
    try:
        previous = json.loads(memory_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise MemoryWriteError("target MEMORY.json is invalid") from exc
    if not isinstance(previous, dict):
        raise MemoryWriteError("target MEMORY.json must contain an object")
    changed: list[str] = []
    conflicts: list[str] = []
    resulting = _merge(previous, updates, changed, conflicts)
    previous_bytes = _canonical(previous)
    resulting_bytes = _canonical(resulting)
    temporary = memory_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(resulting, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(memory_path)
    audit = MemoryWriteAudit(
        run_id=context.manifest.run_id,
        executor_agent_id=context.identity.agent_id,
        target_layer=str(target),
        memory_path=str(memory_path),
        previous_sha256=hashlib.sha256(previous_bytes).hexdigest(),
        resulting_sha256=hashlib.sha256(resulting_bytes).hexdigest(),
        changed_fields=sorted(changed),
        conflicting_fields=sorted(conflicts),
    )
    audit_root = Path(audit_directory).expanduser().resolve()
    audit_root.mkdir(parents=True, exist_ok=True)
    audit_path = audit_root / f"{context.manifest.run_id}-memory.json"
    audit_path.write_text(audit.model_dump_json(indent=2) + "\n")
    return audit


def _merge(base: dict[str, Any], updates: dict[str, Any], changed: list[str], conflicts: list[str], prefix: str = "") -> dict[str, Any]:
    result = dict(base)
    for key, value in updates.items():
        field = f"{prefix}.{key}" if prefix else key
        old = result.get(key)
        if isinstance(old, dict) and isinstance(value, dict):
            result[key] = _merge(old, value, changed, conflicts, field)
        elif old != value:
            changed.append(field)
            if key in result:
                conflicts.append(field)
            if value is None:
                result.pop(key, None)
            else:
                result[key] = value
    return result


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
