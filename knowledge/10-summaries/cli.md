---
id: cli
type: entity
status: active
updated: 2026-09-01
tags: [locate, cli, lifecycle]
depends_on:
  - "[[control-plane]]"
  - "[[agent-suite]]"
related:
  - "[[agenty-architecture]]"
---

# cli

## entry

- `src/agenty/cli.py` — argparse 命令树、Rich 输出与错误边界
- `src/agenty/runtime.py` — `start` 的执行实现
- `src/agenty/workspace.py` — `workspace create` 与 `migrate` 实现

## reads

| 任务类型 | 必读（按顺序） |
| --- | --- |
| develop 新命令 | `cli.py:build_parser` → 对应领域模块 → `test_cli.py` |
| fix 参数解析 | `cli.py:build_parser` → `test_cli.py` |
| fix 生命周期显示 | `cli.py:cmd_show` → `state.py` |
| fix doctor | `cli.py:cmd_doctor` → `suite.py:inspect_suite` |

## tests

- `tests/test_cli.py`

## symptoms

| 症状 | 先看 |
| --- | --- |
| runtime 参数被 argparse 吃掉 | `runtime add`/`start` 的 `argparse.REMAINDER` |
| 命令错误未返回非零 | `main` 的 `AgentyError` 边界 |
| list/show 状态不同 | `AgentStateMachine.load` 与 binding 读取 |

## related

- 总体定位见 [[agenty-architecture]]。
