"""Agenty CLI entry point."""

import platform
import sys

import questionary
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agenty import __version__

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


def cmd_version(_args):
    """Show version info."""
    table = Table(show_header=False, border_style="blue")
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")
    table.add_row("Version", __version__)
    table.add_row("Python", sys.version.split()[0])
    table.add_row("OS", f"{platform.system()} {platform.release()}")
    table.add_row("Arch", platform.machine())
    console.print(Panel(table, title="agenty", border_style="blue"))


def cmd_run(args):
    """Run a demo agent task."""
    task = args.task or "greet"
    if task == "greet":
        console.print(Panel(
            "Hi! I'm [bold]agenty[/bold], your demo agent.\n"
            "Use [cyan]agenty chat[/cyan] to start an interactive session.",
            title="Agent",
            border_style="green",
        ))
    elif task == "think":
        console.print(Panel(
            "Thinking... Done! The answer is [bold yellow]42[/bold yellow].",
            title="Agent",
            border_style="green",
        ))
    elif task == "status":
        table = Table(show_header=False, border_style="green")
        table.add_column("Key", style="bold")
        table.add_column("Value")
        table.add_row("Platform", platform.system())
        table.add_row("Status", "[bold green]Operational[/bold green]")
        table.add_row("Uptime", "Since last install")
        console.print(Panel(table, title="Agent Status", border_style="green"))


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


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="agenty",
        description="A demo agent CLI built with uv",
    )
    parser.add_argument("--version", action="store_true", help="Show version")
    sub = parser.add_subparsers(dest="command")

    # hello
    p_hello = sub.add_parser("hello", help="Say hello")
    p_hello.add_argument("name", nargs="?", help="Your name")

    # run
    p_run = sub.add_parser("run", help="Run a demo agent task")
    p_run.add_argument("task", nargs="?", default="greet",
                       choices=["greet", "think", "status"],
                       help="Task to run (default: greet)")

    # chat
    sub.add_parser("chat", help="Start an interactive chat session")

    args = parser.parse_args()

    if args.version:
        cmd_version(args)
    elif args.command == "hello":
        cmd_hello(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "chat":
        cmd_chat(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
