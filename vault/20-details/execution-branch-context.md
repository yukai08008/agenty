---
id: execution-branch-context
type: decision
status: active
updated: 2026-09-05
tags: [agenty, session, environment, strategy, reward]
part_of:
  - "[[agenty-state-machines]]"
depends_on:
  - "[[dual-machine-boundary]]"
related:
  - "[[runtime-state-event-baseline]]"
---

# Decision: Bind execution branches to session and environment

## Decision

Agenty 的执行分支不能只由 Runtime Session fork 表示。一个可恢复、可比较的执行分支必须同时绑定 Runtime Session lineage 和项目 Environment，并可追踪 `Env → Action(strategy) → Env' → Reward`。

## Consequences

- Runtime 原生 Session fork 只是底层可选能力，不能承担完整分支语义。
- Session 恢复或分叉时必须同时验证项目环境身份。
- Env、Action/Strategy、Reward 成为后续协议的一等概念。
- Reward 不预设为单一标量；表示、评价和聚合方法后续再定。
- 文件系统隔离不能由 Session fork 推断，需要 Agenty 单独设计。

## Open questions

完整需求及未决项记录在 `docs/execution-branch-context.md`。该需求不扩展 v0.01-a，后续版本排期尚未确定。
