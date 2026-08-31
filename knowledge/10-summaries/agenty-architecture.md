---
id: agenty-architecture
type: summary
status: active
updated: 2026-09-01
tags: [agenty, architecture, agent]
implements: "[[decision-multi-agent-control-plane]]"
related:
  - "[[00-index/locate|Development locate map]]"
---

# Agenty architecture

## Summary

Agenty 是外部 Agent runtime 的多 Agent 生命周期与状态管理层。它不创建模型能力，而是登记已有 Agent、保存每个 Agent 的可恢复状态机上下文、创建通用 Worker，并将 Worker 安全迁移为 Git 项目 Agent。

## Current state

- `~/.agenty` 是 N 个 Agent 共享的本地控制面；
- 每个 Agent 使用不可变 ID，并拥有隔离的 metadata、binding、state、checkpoint、runtime 和诊断日志；
- agent suite 位于 Worker 或项目目录，不存放在控制面；
- Agent 知识保存在 suite，Agenty 运行状态保存在控制面；
- v1.01 聚焦 API、状态协议和 CLI，不包含 Web 与 daemon。

## Relationships

详细边界由 [[decision-multi-agent-control-plane]] 确立。代码入口通过 [[00-index/locate|Development locate map]] 渐进定位。

## Details

- `dev_plans/legacy-v1.01/PRD.md`
- `pm-state.md`
