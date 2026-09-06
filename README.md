# agenty

[中文文档](README_zh.md)

> Agenty is evolving from the early demo CLI into an agent system with reasoning, memory, and multiple runtime adapters. See [`ROADMAP.md`](ROADMAP.md) for goals, [`pm-state.md`](pm-state.md) for current progress, [`CHANGELOG.md`](CHANGELOG.md) for completed changes, and [`AGENTS.md`](AGENTS.md) for the handoff contract. The content below primarily describes the existing early CLI.

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

# Run demo agent tasks
agenty run           # default: greet
agenty run greet     # say hi
agenty run think     # deep thoughts
agenty run status    # system status

# Start interactive chat
agenty chat

# Show help
agenty --help
```

## How It Works

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
