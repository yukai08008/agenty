---
id: decision-multi-agent-control-plane
type: decision
status: active
updated: 2026-09-01
tags: [agenty, decision, state-machine]
related:
  - "[[agenty-architecture]]"
---

# Multi-Agent control plane and project suite separation

## Decision

`~/.agenty` 是 Agenty 的多 Agent 控制面，而不是某个默认 Agent 的 home 或 agent suite。每个 Agent 的身份、binding、状态快照、事件、checkpoint、runtime handle 和诊断日志按不可变 Agent ID 隔离保存。

Agent suite 位于具体 Worker 或 Git 项目根内，保存 `AGENTS.md`、`MEMORY.json`、skills、memory、sessions 和语义 agent log。

## Rationale

- Agenty 对应 N 个 Agent，单默认 Agent 模型无法表达并发和隔离；
- 控制面状态需要跨 CLI 进程恢复，但不应污染项目知识；
- suite 需要随项目存在和演化，不能被隐藏在用户 home 中；
- Worker 在项目化前也需要完整 suite，因此 suite 属于活动工作空间，而不是只属于 Git。

## Consequences

- 所有 Agent 操作先解析稳定 ID；
- `~/.agenty` 丢失会损失本机执行连续性，但不会删除项目知识；
- 项目丢失时控制面不能代替 suite；
- lifecycle、execution、task 状态必须分轴表达；
- Worker→Project 迁移只改变 binding，不改变 Agent ID 和状态历史。

## Deferred decisions

- 同一 Git 项目中 N 个 Agent 的 suite 目录布局；
- 跨机器同步控制面状态；
- runtime 私有 session 的统一协议。
