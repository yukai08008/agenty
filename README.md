# agenty

[中文文档](README_zh.md)

> Agenty is evolving from the early demo CLI into an agent system with reasoning, memory, and multiple runtime adapters. `agenty run` now exposes the OpenCode 1.18.26 RuntimeMachine foundation, but it is not yet the complete Anna agent. See [`ROADMAP.md`](ROADMAP.md) for goals, [`pm-state.md`](pm-state.md) for current progress, [`CHANGELOG.md`](CHANGELOG.md) for completed changes, and [`AGENTS.md`](AGENTS.md) for the handoff contract.

A demo agent CLI built with uv — showcasing how to create a Python CLI tool that installs on both Linux and macOS with a single command.

## One-line Install

```bash
curl -fsSL https://raw.githubusercontent.com/yukai08008/agenty/main/install.sh | bash
```

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/yukai08008/agenty/main/install.sh | bash -s -- uninstall
```

## Install with uv directly

If you already have [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/yukai08008/agenty.git
```

## Usage

```bash
# Show version and system info
agenty --version

# Say hello
agenty hello
agenty hello Alice

# Run a natural-language task with exact OpenCode 1.18.26
agenty run "Summarize this repository"

# Allow non-interactive tool execution for this Turn
agenty run "Inspect disk usage without changing files" --auto-approve

# Bind a different working directory and print the full TurnResult JSON
agenty run "Review this project" -C /path/to/project --json

# Start interactive chat
agenty chat

# Show help
agenty --help
```

## How It Works

`agenty run` selects exact OpenCode 1.18.26, probes its capabilities, builds a RuntimeTurnRequest, and returns an auditable TurnResult containing the terminal state, output, Session, usage, changed-file observations, and normalized/raw evidence-log references. Tool automation is disabled unless `--auto-approve` is explicitly supplied.

The command currently provides a minimal Runtime-backed application entry point. AgentyMachine, Anna identity, hierarchical memory/skills, and long-term result storage remain under development.

Run `agenty run --help` for timeout, executable-path, working-directory, and JSON options.

## Installation

The install script (`install.sh`) does three things:

1. **Installs uv** (if not present) — a fast Python package manager
2. **Ensures `~/.local/bin` is in PATH** — the standard user-level bin directory
3. **Installs agenty via `uv tool install`** — isolated environment, no dependency conflicts

Since Python source code is cross-platform and uv handles virtual environments automatically, the same script works identically on Linux and macOS with zero platform-specific logic.

## Project Structure

```
agenty/
├── install.sh          # One-line install script
├── pyproject.toml      # Project config + CLI entry point
├── README.md
└── src/
    └── agenty/
        ├── __init__.py  # Version
        └── cli.py       # CLI commands
```

## Development

```bash
# Clone
git clone https://github.com/yukai08008/agenty.git
cd agenty

# Run directly with uv (no install needed)
uvx --from . agenty --version

# Or install locally
uv tool install --force .
```
