---
id: agent-harness-architecture
type: architecture
status: active
updated: 2026-09-11
tags: [agenty, agent-harness, context, memory, skills]
related:
  - "[[agenty-state-machines]]"
  - "[[dual-machine-boundary]]"
  - "[[execution-branch-context]]"
---

# Agent Harness 架构

## Summary

Agent Harness 是 Agenty 顶层 Agent 的运行控制面：提供完整 Agent Workspace、递归上下文解析、任务注册、分级唤起、权限边界、审计清单和分层写回。RuntimeMachine 是执行后端，不等于 Agent 本体。

## Decisions

- 每个可执行 Agent 必须拥有 Identity、AGENTS、Memory、Skills、Task 和运行记录等完整边界。
- 上下文按根 → 公共 agents → 具体 Agent → 项目/任务递归解析；近层覆盖远层，但不能扩大环境和上级授权。
- 凭据不自动继承；每次执行生成不含秘密正文的 `context_manifest`。
- 模型输出只能形成 Decision/ActionIntent，外部副作用必须经过 deliver 授权门。
- L0/L1/L2/L3 分级唤起与同一 Agent 身份绑定，证据使用同一 run_id 关联。

## Implementation boundary

当前仓库已完成 RuntimeMachine 六类职责和最小 `agenty run`；Workspace、Context Resolver、Task Registry、AgentyMachine、分级唤起和 Anna 尚未实现。

详细设计见 [`docs/agent-harness.md`](../../docs/agent-harness.md)。
