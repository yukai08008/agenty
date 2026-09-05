---
id: runtime-turn-contract
type: decision
status: active
updated: 2026-09-06
tags: [agenty, runtime, turn, state-machine]
part_of:
  - "[[agenty-state-machines]]"
depends_on:
  - "[[runtime-state-event-baseline]]"
  - "[[execution-branch-context]]"
related:
  - "[[runtime-capability-scope]]"
---

# Decision: Bind every runtime turn to explicit context

## Decision

每个 Runtime Turn 由独立 TurnMachine 管理，并使用中立 RuntimeEvent 驱动。请求必须包含 turn ID、correlation ID、prompt 和工作目录；Runtime 首次返回 Session ID 后，同一 Turn 的后续事件必须保持一致。

## Boundary

工作目录只是首次调用的最低环境绑定，不是完整 ProjectEnvironment identity。v0.03 只允许新建 Session；Environment 快照及校验完成前，不开放 resume/fork。

## Implementation

v0.03-a 已实现 Pydantic `RuntimeTurnRequest`、`TurnStateData` 和普通 Python `TurnMachine`。状态机验证生命周期、事件域、Runtime、Turn、correlation 和 Session 上下文，失败与超时要求结构化 RuntimeFailure。

v0.03-b 已实现通用 RuntimeTurnRunner 与 OpenCode 1.18.26 JSONL Adapter。当前只允许在显式工作目录中新建 Session；prompt 由 CLI 参数分隔符保护，默认不启用 auto、resume 或 fork。假进程集成测试覆盖成功、错误、畸形输出、非零退出与超时；真实模型验证仍属于 v0.03-c。
