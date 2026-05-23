"""Agenty CLI entry point."""

import argparse
import platform
import sys

from agenty import __version__


def cmd_hello(args):
    """Say hello from agenty."""
    name = args.name or "World"
    print(f"Hello, {name}! Agenty is running.")


def cmd_version(_args):
    """Show version info."""
    print(f"agenty {__version__}")
    print(f"  Python:  {sys.version.split()[0]}")
    print(f"  OS:      {platform.system()} {platform.release()}")
    print(f"  Arch:    {platform.machine()}")


def cmd_run(args):
    """Run a demo agent task."""
    task = args.task or "greet"
    if task == "greet":
        print("Agent: Hi! I'm agenty, your demo agent.")
    elif task == "think":
        print("Agent: Thinking... Done! The answer is 42.")
    elif task == "status":
        print(f"Agent: All systems operational on {platform.system()}.")
    else:
        print(f"Agent: Unknown task '{task}'. Try: greet, think, status")


def main():
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

    args = parser.parse_args()

    if args.version:
        cmd_version(args)
    elif args.command == "hello":
        cmd_hello(args)
    elif args.command == "run":
        cmd_run(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
