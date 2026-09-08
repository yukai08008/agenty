# v0.06 PRD - Minimal Runtime-backed CLI

> Milestone: M1 Anna
> Parent baseline: `v0.05-f@8586376`
> Draft date: 2026-09-08
> Type: user-facing delivery
> Scope source: user acceptance of v0.05-f and request for `agenty run`

## 0. One-line goal

Expose the completed RuntimeMachine foundation through a minimal `agenty run "task"` command that selects exact OpenCode 1.18.26 and returns an auditable Turn result.

## 1. Scope and invariants

### 1.1 In scope

- Replace the early fixed demo tasks behind `agenty run` with natural-language task execution.
- Select OpenCode by Runtime type and exact Adapter version before every Turn.
- Bind the Turn to an explicit working directory.
- Enforce an effective deny-all OpenCode permission policy unless the user passes `--auto-approve`.
- Support a Runtime timeout, an alternate OpenCode executable, human-readable output, full JSON output, and meaningful process exit codes.
- Cover the application boundary with offline fake-Adapter tests.
- Perform one explicitly authorized live OpenCode acceptance run.

### 1.2 Out of scope

- AgentyMachine lifecycle, Environment/Action/Reward, and Agent identity.
- `agents/anna/`, hierarchical constraints, memory, and skills.
- Model/effort flags and Runtime Session resume from the CLI.
- Interactive approval round trips or a replacement for the early `chat` command.
- Long-term result and event-log retention.

### 1.3 Invariants

- The CLI uses RuntimeMachine public selection, request, Runner, and Result contracts rather than invoking vendor commands directly.
- OpenCode behavior remains bound to exact version 1.18.26 and `transient_process`.
- Tool automation is explicit; deny mode disables project configuration, plugins, external skills, and resolved MCP entries, then validates the final dedicated Agent permission before starting the Turn. `--auto-approve` is never inferred from the prompt.
- Default automated tests do not call a real model.
- Runtime data is not tracked by Git.
- This command is a minimal application entry point, not a claim that Anna or AgentyMachine is complete.

## 2. Command contract

```text
agenty run TASK... [-C DIRECTORY] [--auto-approve]
                  [--timeout SECONDS] [--opencode PATH] [--json]
```

Exit codes:

- `0`: Turn succeeded.
- `1`: Runtime was selected and the Turn reached a non-success terminal state.
- `2`: Runtime selection failed before a Turn result existed.

## 3. Feature split

1. `v0.06-a`: minimal Runtime-backed `agenty run` entry point, tests, documentation, and live acceptance.

## 4. Risks

| ID | Risk | Severity | Mitigation | Owner |
|---|---|---|---|---|
| R1 | A convenient CLI silently enables broad tool permissions | high | Require explicit `--auto-approve`; retain deny-by-default request policy | Coder/Reviewer |
| R2 | The entry point bypasses exact Runtime selection | high | Build it over RuntimeAdapterRegistry and RuntimeSelectionMachine | Coder/Tester |
| R3 | Users mistake the Runtime wrapper for the completed Anna agent | medium | State the boundary in help, docs, roadmap, and changelog | PM/Reviewer |
| R4 | Live validation leaks into the default suite | high | Keep live execution manual and tests fake-Adapter only | Tester |

## 5. Signature

Agent-PM-v0.06
