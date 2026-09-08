"""Agenty CLI entry point."""

import argparse
import json
import math
import platform
import sys

import questionary
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from agenty import __version__
from agenty.config import CONFIG_FILE, ensure_config, get_api_key
from agenty.run import AgentyRunError, run_opencode_task
from agenty.runtime.protocol import TurnState

console = Console()

BANNER = """
  ___              _
 / _ \\ _ __   ___ | |_
| |_| | '_ \\ / _ \\| __|
|  _  | | | | (_) | |_
|_| |_|_| |_|\\___/ \\__|
"""


def cmd_hello(args):
    """Say hello from agenty."""
    name = args.name or "World"
    console.print(Panel(
        f"Hello, [bold green]{name}[/bold green]! Agenty is running.",
        title="agenty",
        border_style="blue",
    ))


def cmd_version(args):
    """Show version info."""
    # Plain text for non-terminal (pipes, scripts)
    if not sys.stdout.isatty():
        print(f"agenty {__version__}")
        return
    table = Table(show_header=False, border_style="blue")
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")
    table.add_row("Version", __version__)
    table.add_row("Python", sys.version.split()[0])
    table.add_row("OS", f"{platform.system()} {platform.release()}")
    table.add_row("Arch", platform.machine())
    console.print(Panel(table, title="agenty", border_style="blue"))


def cmd_run(args):
    """Run one task through the version-bound OpenCode RuntimeMachine."""
    try:
        result = run_opencode_task(
            " ".join(args.task),
            working_directory=args.directory,
            auto_approve=args.auto_approve,
            timeout_seconds=args.timeout,
            executable=args.opencode,
        )
    except AgentyRunError as exc:
        failure = exc.failure
        if args.json:
            print(failure.model_dump_json())
        else:
            console.print(
                Panel(
                    f"{failure.message}\n\nCode: {failure.code.value}",
                    title="Run Setup Failed",
                    border_style="red",
                )
            )
        return 2
    except KeyboardInterrupt:
        if args.json:
            print(json.dumps({"state": "interrupted", "exit_code": 130}))
        else:
            console.print(
                "\n[bold yellow]Turn interrupted; OpenCode was stopped.[/bold yellow]"
            )
        return 130

    if args.json:
        print(result.model_dump_json())
    else:
        if result.output_text:
            console.print(Markdown(result.output_text))
        if result.failure is not None:
            console.print(
                Panel(
                    f"{result.failure.message}\n\nCode: {result.failure.code.value}",
                    title="Turn Failed",
                    border_style="red",
                )
            )
        table = Table(show_header=False, border_style="blue")
        table.add_column("Key", style="bold cyan")
        table.add_column("Value")
        table.add_row("State", result.state.value)
        table.add_row(
            "Runtime",
            f"{result.runtime.runtime_kind} {result.runtime.runtime_version}",
        )
        table.add_row("Session", result.session_id or "-")
        table.add_row("Tokens", str(result.usage.total_tokens))
        table.add_row("Cost", f"{result.usage.cost} {result.usage.currency}")
        table.add_row("Changed files", str(len(result.artifacts.artifacts)))
        table.add_row("Normalized log", result.event_log.normalized_path)
        table.add_row("Raw log", result.event_log.raw_path)
        console.print(Panel(table, title="Agenty Turn", border_style="blue"))
    return 0 if result.state is TurnState.SUCCEEDED else 1


def cmd_upgrade(_args):
    """Upgrade agenty to the latest version."""
    import subprocess

    console.print(Panel(
        f"Current version: [bold cyan]{__version__}[/bold cyan]\n"
        "Upgrading...",
        title="agenty upgrade",
        border_style="yellow",
    ))

    result = subprocess.run(
        ["uv", "tool", "upgrade", "agenty"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        # Get new version via --version (plain text when piped)
        new_version = __version__
        try:
            new_result = subprocess.run(
                ["agenty", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            if new_result.returncode == 0 and new_result.stdout.strip():
                # Output: "agenty 0.2.0"
                parts = new_result.stdout.strip().split()
                if len(parts) >= 2:
                    new_version = parts[1]
        except OSError:
            pass

        if new_version != __version__:
            console.print(Panel(
                f"Upgraded: [bold red]{__version__}[/bold red] → [bold green]{new_version}[/bold green]",
                title="Upgrade Complete",
                border_style="green",
            ))
        else:
            console.print(Panel(
                f"Already on the latest version: [bold green]{__version__}[/bold green]",
                title="Upgrade Complete",
                border_style="green",
            ))
    else:
        console.print(Panel(
            f"Upgrade failed:\n{result.stderr.strip() or result.stdout.strip()}",
            title="Upgrade Failed",
            border_style="red",
        ))
        raise SystemExit(1)


def cmd_config(_args):
    """Show or initialize config."""
    path = ensure_config()
    if path:
        console.print(Panel(
            f"Config file created at: [bold cyan]{path}[/bold cyan]\n\n"
            "Edit it to add your API key:\n"
            f"  [bold]{path}[/bold]\n\n"
            "Or set environment variable:\n"
            "  [bold]export AGENT_API_KEY=your_key[/bold]",
            title="agenty config",
            border_style="blue",
        ))
    else:
        console.print(Panel(
            f"Config file: [bold cyan]{CONFIG_FILE}[/bold cyan]\n\n"
            f"API key: {'[bold green]set[/bold green]' if get_api_key() else '[bold red]not set[/bold red]'}\n\n"
            "Edit config:\n"
            f"  [bold]{CONFIG_FILE}[/bold]",
            title="agenty config",
            border_style="blue",
        ))


def cmd_chat(_args):
    """Start an interactive chat session."""
    console.print(BANNER, style="bold blue")
    console.print(Panel(
        "Welcome to [bold]agenty[/bold] chat!\n"
        "Type your message and press Enter. Type [bold red]quit[/bold red] to exit.",
        border_style="blue",
    ))

    while True:
        try:
            user_input = questionary.text("You>").ask()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input or user_input.strip().lower() in ("quit", "exit", "q"):
            console.print(Panel("Goodbye!", border_style="blue"))
            break

        # Simple demo responses
        text = user_input.strip().lower()
        if "hello" in text or "hi" in text:
            reply = "Hey there! How can I help you?"
        elif "name" in text:
            reply = "I'm **agenty**, a demo agent CLI built with uv."
        elif "help" in text:
            reply = (
                "I can respond to a few things:\n"
                "- Say **hello** and I'll greet you\n"
                "- Ask my **name** and I'll tell you\n"
                "- Ask for **status** and I'll check systems\n"
                "- Type **quit** to exit"
            )
        elif "status" in text:
            reply = f"All systems operational on **{platform.system()}**."
        else:
            reply = f"I heard you say: _{user_input.strip()}_\nI'm a demo agent, so my responses are limited. Try asking for **help**!"

        console.print(Panel(
            Markdown(reply),
            title="Agent",
            border_style="green",
        ))


def _positive_float(value):
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive and finite")
    return parsed


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="agenty",
        description="Run auditable agent tasks through version-bound runtimes",
    )
    parser.add_argument("--version", action="store_true", help="Show version")
    sub = parser.add_subparsers(dest="command")

    # hello
    p_hello = sub.add_parser("hello", help="Say hello")
    p_hello.add_argument("name", nargs="?", help="Your name")

    # run
    p_run = sub.add_parser("run", help="Run a task with OpenCode 1.18.26")
    p_run.add_argument("task", nargs="+", help="Natural-language task")
    p_run.add_argument(
        "-C",
        "--directory",
        default=".",
        help="Working directory bound to the turn (default: current directory)",
    )
    p_run.add_argument(
        "--auto-approve",
        action="store_true",
        help="Allow OpenCode to execute tools without an approval round trip",
    )
    p_run.add_argument(
        "--timeout",
        type=_positive_float,
        default=300,
        metavar="SECONDS",
        help="Runtime timeout in seconds (default: 300)",
    )
    p_run.add_argument(
        "--opencode",
        default="opencode",
        metavar="PATH",
        help="OpenCode executable name or path",
    )
    p_run.add_argument(
        "--json",
        action="store_true",
        help="Print the complete TurnResult as JSON",
    )

    # chat
    sub.add_parser("chat", help="Start an interactive chat session")

    # upgrade
    sub.add_parser("upgrade", help="Upgrade agenty to the latest version")

    # config
    sub.add_parser("config", help="Show or initialize configuration")

    args = parser.parse_args(argv)

    if args.version:
        cmd_version(args)
        return 0
    elif args.command == "hello":
        cmd_hello(args)
        return 0
    elif args.command == "run":
        return cmd_run(args)
    elif args.command == "chat":
        cmd_chat(args)
        return 0
    elif args.command == "upgrade":
        cmd_upgrade(args)
        return 0
    elif args.command == "config":
        cmd_config(args)
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
