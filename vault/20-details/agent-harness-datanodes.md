---
id: agent-harness-datanodes
type: decision
status: active
updated: 2026-09-12
tags: [agenty, datanode, harness, agent-machine]
related:
  - "[[agent-harness-architecture]]"
  - "[[dual-machine-boundary]]"
  - "[[execution-branch-context]]"
---

# Agent Harness DataNode 决策

## Summary

Harness 的稳定节点分为业务类和运行类。业务类节点是 Agent 身份、目标、交付结果和记忆事实；运行类节点是任务定义、上下文清单、执行实例、Runtime Turn 和授权决定。运行节点服务业务结果，但不能复制或冒充业务事实。

## Current boundary

现有 `Goal`、`TaskSpec`、`ContextManifest`、`AgentSnapshot`、`TurnResult` 和 `MemoryWriteAudit` 已有部分实现，但其中若干是组合 DTO 或运行记录，不应直接当成最终业务节点。详细节点身份、不变量、关系和未决取舍见 [`docs/agent-harness-datanodes.md`](../../docs/agent-harness-datanodes.md)。

## Next decision gate

在进入 FSM 和持久化前，先确认 `AgentOutcome`、`MemoryFact`、`AgentExecution` 的最小字段及 `AuthorizationDecision` 的账本边界。
