"""Minimal Agent Harness context resolution and manifest generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HarnessError(ValueError):
    """A context cannot be safely resolved for execution."""


class AgentIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    name: str
    role: str | None = None
    parent_agent_id: str | None = None


class ContextResource(BaseModel):
    path: str
    kind: str
    sha256: str


class ContextManifest(BaseModel):
    schema_version: int = 1
    run_id: str
    executor_agent_id: str
    loaded_layers: list[str]
    resources: list[ContextResource]
    selected_skills: list[str] = Field(default_factory=list)
    overrides: list[dict[str, str]] = Field(default_factory=list)
    effective_identity: AgentIdentity
    effective_permissions: dict[str, Any] = Field(default_factory=dict)
    manifest_sha256: str = ""


class ResolvedContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    identity: AgentIdentity
    instructions: str
    memory: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    skills: dict[str, str] = Field(default_factory=dict)
    permissions: dict[str, Any] = Field(default_factory=dict)
    manifest: ContextManifest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(f"invalid JSON resource: {path}") from exc
    if not isinstance(value, dict):
        raise HarnessError(f"JSON resource must contain an object: {path}")
    return value


def _safe_layer(root: Path, candidate: Path) -> Path:
    expanded = candidate.expanduser()
    resolved = (expanded if expanded.is_absolute() else root / expanded).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise HarnessError(f"path escapes workspace root: {candidate}") from exc
    return resolved


def resolve_context(
    workspace_root: str | Path,
    *,
    agent_root: str | Path,
    task_directory: str | Path | None = None,
    run_id: str = "context-resolution",
) -> ResolvedContext:
    """Resolve a deterministic, auditable context from nearest layers."""
    root = Path(workspace_root).expanduser().resolve()
    agent = _safe_layer(root, Path(agent_root))
    layers = [root]
    public = root / "agents"
    if public.exists() and public != agent:
        layers.append(public)
    if agent != root:
        layers.append(agent)
    if task_directory is not None:
        task = _safe_layer(root, Path(task_directory))
        if task not in layers:
            layers.append(task)

    resources: list[ContextResource] = []
    instructions: list[str] = []
    memory: dict[str, Any] = {}
    config: dict[str, Any] = {}
    skills: dict[str, str] = {}
    identity_data: dict[str, Any] = {}
    permissions: dict[str, Any] = {}
    overrides: list[dict[str, str]] = []

    for index, layer in enumerate(layers):
        required = index == len(layers) - 1 or layer == agent
        agents_file = layer / "AGENTS.md"
        identity_file = layer / "Identity.md"
        memory_file = layer / "MEMORY.json"
        if required and (not agents_file.is_file() or not identity_file.is_file() or not memory_file.is_file()):
            raise HarnessError(f"agent layer is incomplete: {layer}")
        if agents_file.is_file():
            instructions.append(agents_file.read_text())
            resources.append(ContextResource(path=str(agents_file), kind="instructions", sha256=_sha256(agents_file)))
        if identity_file.is_file():
            current = _read_identity(identity_file)
            if identity_data:
                overrides.append({"field": "identity", "from_layer": str(layer), "to_layer": str(layer)})
            identity_data.update(current)
            resources.append(ContextResource(path=str(identity_file), kind="identity", sha256=_sha256(identity_file)))
        if memory_file.is_file():
            memory = _deep_merge(memory, _read_json(memory_file))
            resources.append(ContextResource(path=str(memory_file), kind="memory", sha256=_sha256(memory_file)))
        for directory, target in ((layer / "config", config), (layer / "skills", skills)):
            if directory.is_dir():
                for item in sorted(directory.iterdir()):
                    if item.name.startswith(".") or not item.is_file() or item.name == "SKILL_INDEX.md":
                        continue
                    if directory.name == "config" and item.suffix == ".json":
                        values = _read_json(item)
                        if "permissions" in values:
                            permissions = _restrict_permissions(permissions, values["permissions"])
                            values = {key: value for key, value in values.items() if key != "permissions"}
                        target.update(values)
                    elif directory.name == "skills" and item.suffix.lower() in {".md", ".yaml", ".yml"}:
                        target[item.stem] = str(item)
                    resources.append(ContextResource(path=str(item), kind=directory.name, sha256=_sha256(item)))

    identity = AgentIdentity.model_validate(identity_data)
    resources.sort(key=lambda item: (item.path, item.kind))
    manifest = ContextManifest(
        run_id=run_id,
        executor_agent_id=identity.agent_id,
        loaded_layers=[str(layer) for layer in layers],
        resources=resources,
        selected_skills=sorted(skills),
        overrides=overrides,
        effective_identity=identity,
        effective_permissions=permissions,
    )
    canonical = manifest.model_dump(exclude={"manifest_sha256"}, mode="json")
    manifest.manifest_sha256 = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return ResolvedContext(
        identity=identity,
        instructions="\n\n".join(instructions),
        memory=memory,
        config=config,
        skills=skills,
        permissions=permissions,
        manifest=manifest,
    )


def _restrict_permissions(current: dict[str, Any], requested: Any) -> dict[str, Any]:
    """Apply a child permission declaration without expanding its parent ceiling."""
    if not isinstance(requested, dict):
        raise HarnessError("permissions must be an object")
    if not current:
        return dict(requested)
    result = dict(current)
    for key, value in requested.items():
        if key not in result:
            continue
        ceiling = result[key]
        if isinstance(ceiling, list) and isinstance(value, list):
            result[key] = sorted(set(ceiling).intersection(value))
        elif isinstance(ceiling, bool) and isinstance(value, bool):
            result[key] = ceiling and value
        elif ceiling != value:
            raise HarnessError(f"permission declaration conflicts with parent ceiling: {key}")
    return result


def _read_identity(path: Path) -> dict[str, Any]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if line.startswith("-") and ":" in line:
            key, value = line[1:].split(":", 1)
            normalized = key.strip().replace(" ", "_").lower()
            values[normalized] = value.strip().strip("`")
    if not values:
        raise HarnessError(f"identity file has no fields: {path}")
    return values
