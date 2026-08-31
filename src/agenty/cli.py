"""Agenty command-line interface."""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agenty import __version__
from agenty.runtime import launch_agent
from agenty.state import AgentStateMachine
from agenty.store import AgentyError, AgentyStore
from agenty.suite import create_project_snapshot, inspect_suite
from agenty.workspace import create_worker, migrate_worker


console = Console()


def make_store(args: argparse.Namespace) -> AgentyStore:
    return AgentyStore(home=args.home, agents_home=args.agents_home)


def cmd_init(args: argparse.Namespace) -> None:
    store = make_store(args)
    detected = store.initialize()
    names = ", ".join(profile["name"] for profile in detected) or "none"
    console.print(
        Panel(
            f"Control plane: [cyan]{store.home}[/cyan]\n"
            f"Default Worker root: [cyan]{store.agents_home}[/cyan]\n"
            f"Detected runtimes: {names}",
            title="Agenty initialized",
            border_style="green",
        )
    )


def cmd_runtime_list(args: argparse.Namespace) -> None:
    store = make_store(args)
    table = Table("Name", "Command")
    for profile in store.list_runtimes():
        table.add_row(profile["name"], " ".join(profile["argv"]))
    console.print(table)


def cmd_runtime_add(args: argparse.Namespace) -> None:
    store = make_store(args)
    argv = list(args.argv)
    if argv[:1] == ["--"]:
        argv = argv[1:]
    profile = store.add_runtime(args.name, argv, overwrite=args.force)
    console.print(
        Panel(
            f"{profile['name']}: {' '.join(profile['argv'])}",
            title="Runtime saved",
            border_style="green",
        )
    )


def cmd_claim(args: argparse.Namespace) -> None:
    store = make_store(args)
    agent = store.claim(args.name, args.runtime)
    console.print(
        Panel(
            f"Agent ID: [cyan]{agent.agent_id}[/cyan]\n"
            f"Name: {agent.name}\nRuntime: {agent.runtime}\nPhase: CLAIMED",
            title="Agent claimed",
            border_style="green",
        )
    )


def cmd_list(args: argparse.Namespace) -> None:
    store = make_store(args)
    store.require_initialized()
    table = Table("Agent ID", "Name", "Phase", "Execution", "Runtime", "Root")
    for agent in store.list_agents():
        state = AgentStateMachine(agent.directory).load()
        table.add_row(
            agent.agent_id,
            agent.name,
            state["lifecycle"]["phase"],
            state["execution"]["status"],
            agent.runtime,
            str(agent.bindings.get("active_root") or "-"),
        )
    console.print(table)


def cmd_show(args: argparse.Namespace) -> None:
    store = make_store(args)
    agent = store.resolve_agent(args.agent)
    state = AgentStateMachine(agent.directory).load()
    table = Table(show_header=False)
    rows = (
        ("Agent ID", agent.agent_id),
        ("Name", agent.name),
        ("Runtime", agent.runtime),
        ("Lifecycle", state["lifecycle"]["phase"]),
        ("Execution", state["execution"]["status"]),
        ("Task", state["task"]["status"]),
        ("Revision", str(state["revision"])),
        ("Root", str(agent.bindings.get("active_root") or "-")),
        ("Checkpoint", str(state["recovery"].get("last_checkpoint") or "-")),
    )
    for key, value in rows:
        table.add_row(key, value)
    console.print(Panel(table, title=agent.name, border_style="blue"))


def cmd_workspace_create(args: argparse.Namespace) -> None:
    store = make_store(args)
    agent = create_worker(store, args.agent, args.path)
    console.print(
        Panel(
            f"Agent: {agent.name} ({agent.agent_id})\n"
            f"Worker root: [cyan]{agent.bindings['active_root']}[/cyan]",
            title="Worker created",
            border_style="green",
        )
    )


def cmd_snapshot(args: argparse.Namespace) -> None:
    store = make_store(args)
    agent = store.resolve_agent(args.agent)
    root = agent.bindings.get("active_root")
    if not isinstance(root, str):
        raise AgentyError("Agent has no Worker or Project workspace.")
    machine = AgentStateMachine(agent.directory)
    task_id = f"task_snapshot_{uuid.uuid4().hex}"
    machine.start_task("Create a project snapshot", task_id=task_id)
    try:
        snapshot = create_project_snapshot(root)
        checkpoint_id, _ = machine.checkpoint(
            {
                "snapshot_id": snapshot["snapshot_id"],
                "pending_action": None,
            },
            summary="Project snapshot completed",
        )
        machine.finish_task("COMPLETED")
    except Exception:
        machine.finish_task("FAILED")
        raise
    console.print(
        Panel(
            f"Snapshot: {snapshot['snapshot_id']}\n"
            f"Files: {snapshot['file_count']}\n"
            f"Git: {snapshot['git']['is_work_tree']}\n"
            f"Checkpoint: {checkpoint_id}",
            title="Project snapshot",
            border_style="green",
        )
    )


def cmd_checkpoint(args: argparse.Namespace) -> None:
    store = make_store(args)
    agent = store.resolve_agent(args.agent)
    payload = {"pending_action": args.pending_action}
    checkpoint_id, state = AgentStateMachine(agent.directory).checkpoint(
        payload, summary=args.summary
    )
    console.print(
        Panel(
            f"Checkpoint: [cyan]{checkpoint_id}[/cyan]\nRevision: {state['revision']}",
            title="Agent checkpoint",
            border_style="green",
        )
    )


def cmd_history(args: argparse.Namespace) -> None:
    store = make_store(args)
    agent = store.resolve_agent(args.agent)
    events = AgentStateMachine(agent.directory).history(args.tail)
    table = Table("Revision", "Time", "Event", "Transition")
    for event in events:
        table.add_row(
            str(event.get("revision")),
            str(event.get("timestamp")),
            str(event.get("event")),
            f"{event.get('from')} → {event.get('to')}",
        )
    console.print(table)


def cmd_start(args: argparse.Namespace) -> None:
    store = make_store(args)
    runtime_args = list(args.runtime_args)
    if runtime_args[:1] == ["--"]:
        runtime_args = runtime_args[1:]
    result = launch_agent(store, args.agent, runtime_args, dry_run=args.dry_run)
    if args.dry_run:
        console.print(
            Panel(
                f"Command: {' '.join(result['argv'])}\nCWD: {result['cwd']}",
                title="Runtime dry run",
                border_style="yellow",
            )
        )
    elif result["return_code"] != 0:
        raise SystemExit(int(result["return_code"]))


def cmd_migrate(args: argparse.Namespace) -> None:
    store = make_store(args)
    agent = migrate_worker(store, args.agent, args.target, init_git=args.init_git)
    console.print(
        Panel(
            f"Agent: {agent.name} ({agent.agent_id})\n"
            f"Project: [cyan]{agent.bindings['project']}[/cyan]\n"
            f"Retained source: {agent.bindings['retained_source']}",
            title="Agent migrated",
            border_style="green",
        )
    )


def cmd_doctor(args: argparse.Namespace) -> None:
    store = make_store(args)
    errors: list[str] = []
    if not store.initialized:
        errors.append(f"Control plane is not initialized: {store.home}")
    elif args.agent:
        agent = store.resolve_agent(args.agent)
        state = AgentStateMachine(agent.directory).load()
        root = agent.bindings.get("active_root")
        if state["lifecycle"]["phase"] in {"WORKER", "PROJECT"}:
            if not isinstance(root, str):
                errors.append("Active Agent has no workspace binding")
            else:
                inspection = inspect_suite(root)
                errors.extend(inspection.errors)
                if inspection.agent_id and inspection.agent_id != agent.agent_id:
                    errors.append("Suite agent_id does not match control-plane identity")
        if state["execution"]["runtime_pid"] is not None:
            errors.append("Runtime PID is recorded; live-process verification is not implemented")

    if errors:
        console.print(
            Panel(
                "\n".join(f"- {error}" for error in errors),
                title="Doctor failed",
                border_style="red",
            )
        )
        raise SystemExit(1)
    console.print(Panel("All checked invariants passed.", title="Doctor", border_style="green"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agenty",
        description="Manage multiple external Agents across claimed, Worker, and Project phases.",
    )
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument("--home", type=Path, help="Override AGENTY_HOME")
    parser.add_argument("--agents-home", type=Path, help="Override AGENTY_AGENTS_HOME")
    sub = parser.add_subparsers(dest="command")

    init_parser = sub.add_parser("init", help="Initialize the shared Agenty control plane")
    init_parser.set_defaults(func=cmd_init)

    runtime_parser = sub.add_parser("runtime", help="Manage external runtime profiles")
    runtime_sub = runtime_parser.add_subparsers(dest="runtime_command", required=True)
    runtime_list = runtime_sub.add_parser("list", help="List runtime profiles")
    runtime_list.set_defaults(func=cmd_runtime_list)
    runtime_add = runtime_sub.add_parser("add", help="Add or replace a runtime profile")
    runtime_add.add_argument("--force", action="store_true")
    runtime_add.add_argument("name")
    runtime_add.add_argument("argv", nargs=argparse.REMAINDER)
    runtime_add.set_defaults(func=cmd_runtime_add)

    claim = sub.add_parser("claim", help="Register an existing Agent")
    claim.add_argument("name")
    claim.add_argument("--runtime", required=True)
    claim.set_defaults(func=cmd_claim)

    list_parser = sub.add_parser("list", help="List managed Agents")
    list_parser.set_defaults(func=cmd_list)

    show = sub.add_parser("show", help="Show one Agent and its current state")
    show.add_argument("agent")
    show.set_defaults(func=cmd_show)

    workspace = sub.add_parser("workspace", help="Manage Worker workspaces")
    workspace_sub = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_create = workspace_sub.add_parser("create", help="Create a Worker workspace")
    workspace_create.add_argument("agent")
    workspace_create.add_argument("--path", type=Path)
    workspace_create.set_defaults(func=cmd_workspace_create)

    snapshot = sub.add_parser("snapshot", help="Run the built-in project snapshot scenario")
    snapshot.add_argument("agent")
    snapshot.set_defaults(func=cmd_snapshot)

    checkpoint = sub.add_parser("checkpoint", help="Persist an Agent recovery checkpoint")
    checkpoint.add_argument("agent")
    checkpoint.add_argument("--summary")
    checkpoint.add_argument("--pending-action")
    checkpoint.set_defaults(func=cmd_checkpoint)

    history = sub.add_parser("history", help="Show Agent state transition history")
    history.add_argument("agent")
    history.add_argument("--tail", type=int, default=20)
    history.set_defaults(func=cmd_history)

    start = sub.add_parser("start", help="Start an Agent's configured external runtime")
    start.add_argument("agent")
    start.add_argument("--dry-run", action="store_true")
    start.add_argument("runtime_args", nargs=argparse.REMAINDER)
    start.set_defaults(func=cmd_start)

    migrate = sub.add_parser("migrate", help="Migrate a Worker into a Project root")
    migrate.add_argument("agent")
    migrate.add_argument("target", type=Path)
    migrate.add_argument("--init-git", action="store_true")
    migrate.set_defaults(func=cmd_migrate)

    doctor = sub.add_parser("doctor", help="Validate the control plane or one Agent")
    doctor.add_argument("agent", nargs="?")
    doctor.set_defaults(func=cmd_doctor)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.version:
        print(f"agenty {__version__}")
        return
    if not hasattr(args, "func"):
        parser.print_help()
        return
    try:
        args.func(args)
    except AgentyError as exc:
        console.print(Panel(str(exc), title="Agenty error", border_style="red"))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
