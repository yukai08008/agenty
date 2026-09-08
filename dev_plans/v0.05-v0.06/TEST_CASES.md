# v0.06 TEST_CASES - Minimal Runtime-backed CLI

Status: v0.06-a cases are automated; default cases use a fake Adapter and do not call a real model. CLI-08 also has explicit OpenCode 1.18.26 live evidence.

| ID | Case | Expected | Status |
|---|---|---|---|
| CLI-01 | `agenty run` receives a multi-word task | The joined prompt reaches RuntimeTurnRunner | automated |
| CLI-02 | Detected OpenCode version differs from 1.18.26 | Selection fails before Adapter turn execution | automated |
| CLI-03 | No permission flag is supplied | RuntimeTurnRequest uses `deny_by_default` and OpenCode receives an effective deny-all agent policy | automated and live verified |
| CLI-04 | `--auto-approve` is supplied | Request uses `auto_approve` only after capability validation | automated |
| CLI-05 | `-C` and `--timeout` are supplied | Absolute working directory and positive timeout reach the application runner | automated |
| CLI-06 | `--json` is supplied | Complete serialized TurnResult is written without presentation markup | automated |
| CLI-07 | Turn succeeds, fails, is interrupted, or setup fails | Exit code is `0`, `1`, `130`, or `2` respectively; interrupt reclaims the process group | automated |
| CLI-08 | Explicit live OpenCode task | OpenCode 1.18.26 completes through `agenty run` with Session, usage, evidence logs, and artifact observation | live verified |
