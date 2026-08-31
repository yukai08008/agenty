# Agenty

[中文文档](README_zh.md)

Agenty manages the lifecycle and recoverable state of multiple external Agents. It relies on runtimes such as Codex, OpenCode, and Claude for reasoning and execution.

The v1.01 POC covers three phases:

```text
CLAIMED → WORKER → MIGRATING → PROJECT
```

- `CLAIMED`: an existing Agent is registered in the shared `~/.agenty` control plane.
- `WORKER`: the Agent owns a general workspace, by default under `~/agents/<name>`.
- `PROJECT`: the same Agent identity and suite have been migrated into a Git project.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/yukai08008/agenty/main/install.sh | bash
```

Or install directly with uv:

```bash
uv tool install git+https://github.com/yukai08008/agenty.git
```

## Quick start

```bash
# Initialize the shared multi-Agent control plane
agenty init

# Inspect detected runtimes; add one explicitly when needed
agenty runtime list
agenty runtime add local-codex -- /absolute/path/to/codex

# Register two existing Agents
agenty claim research-worker --runtime local-codex
agenty claim maintenance-worker --runtime local-codex
agenty list

# Create a general Worker and exercise its complete agent suite
agenty workspace create research-worker
agenty snapshot research-worker
agenty checkpoint research-worker --summary "ready for project migration"

# Preview runtime startup
agenty start research-worker --dry-run

# Promote the Worker into a Git project without deleting its source workspace
agenty migrate research-worker ~/mycode/research-project --init-git
agenty doctor research-worker
```

## Storage boundaries

Agenty's shared control plane contains small, per-Agent operational state:

```text
~/.agenty/
├── agents/<agent-id>/
│   ├── metadata.json
│   ├── bindings.json
│   ├── state/current.json
│   ├── state/events.jsonl
│   ├── state/checkpoints/
│   ├── runtime/
│   └── logs/
├── runtimes/
├── locks/
└── logs/
```

The Agent's identity, knowledge, capabilities, sessions, and semantic history live with its Worker or project:

```text
<agent-root>/
├── AGENTS.md -> agent-suite/AGENTS.md
├── agent-suite/
│   ├── AGENTS.md
│   ├── MEMORY.json
│   ├── agent_log.jsonl
│   ├── skills/
│   ├── memory/
│   └── sessions/
└── workspace/
```

Use `AGENTY_HOME` and `AGENTY_AGENTS_HOME` to override the defaults. Tests always use isolated temporary values and never touch the real user control plane.

## State recovery

Each Agent has independent lifecycle, execution, and task state. Every update acquires an Agent-level file lock, increments a revision, appends a full-state JSONL event, and atomically replaces the current snapshot. If the process stops after the event append, Agenty reconstructs `current.json` from the event log.

## Development

```bash
uv run python -m unittest discover -s tests -v
uv build
```

The current project state is in `pm-state.md`. The v1.01 PRD, task card, and tests are under `dev_plans/legacy-v1.01/`.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/yukai08008/agenty/main/install.sh | bash -s -- uninstall
```
