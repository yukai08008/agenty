---
id: dual-machine-boundary
type: decision
status: active
updated: 2026-09-05
tags: [agenty, state-machine, architecture]
part_of:
  - "[[agenty-state-machines]]"
related:
  - "[[agenty-state-machines]]"
---

# Decision: Separate AgentyMachine and RuntimeMachine

## Decision

Agenty 与 Runtime 分别维护独立状态机。Agenty 不吸收 OpenCode、Codex 或 Claude 的内部生命周期；Runtime 也不修改 Agent 的记忆、技能和设计状态。

## Rationale

各 Runtime 都具有模型、effort、会话、窗口、执行和交互能力，内部复杂度足以形成独立状态机。通过命令、事件、能力协商和关联 ID 解耦，才能让双方分别演进。

## Consequences

- Runtime、Session 和 Execution 形成底层层级。
- Agenty 只观察公共事件，并维护自己的任务状态。
- OpenCode 是首个适配实现，但不是公共协议。
- 开发在 Runtime 底层事实和 Agenty 顶层需求之间交替推进。
