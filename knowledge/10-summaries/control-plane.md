---
id: control-plane
type: entity
status: active
updated: 2026-09-01
tags: [locate, control-plane, state-machine]
implements: "[[decision-multi-agent-control-plane]]"
related:
  - "[[agent-suite]]"
  - "[[cli]]"
---

# control-plane

## entry

- `src/agenty/store.py` — home、Agent identity、runtime profile、binding 与原子文件工具
- `src/agenty/state.py` — 三轴状态机、event、checkpoint、锁与恢复
- `src/agenty/runtime.py` — 外部 runtime 启动和 execution 状态闭环

## reads

| 任务类型 | 必读（按顺序） |
| --- | --- |
| develop | `store.py` → `state.py` → `test_store.py` → `test_state.py` |
| fix 状态恢复 | `state.py` → `test_state.py` |
| fix runtime | `runtime.py` → `state.py` → `test_runtime.py` |
| extend 新 runtime | `store.py` → `runtime.py` → `cli.py` |

## tests

- `tests/test_store.py`
- `tests/test_state.py`
- `tests/test_runtime.py`

## symptoms

| 症状 | 先看 |
| --- | --- |
| current revision 落后 | `AgentStateMachine._load_unlocked` |
| 并发 revision 重复 | `file_lock` 与 `_commit_unlocked` |
| Agent 名称冲突 | `AgentyStore.claim` |
| runtime 退出后状态不对 | `launch_agent` |

## related

- 架构边界见 [[decision-multi-agent-control-plane]]。
- suite 文件模型见 [[agent-suite]]。
