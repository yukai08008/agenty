---
id: runtime-capability-scope
type: decision
status: active
updated: 2026-09-05
tags: [agenty, runtime, capability, opencode]
part_of:
  - "[[agenty-state-machines]]"
depends_on:
  - "[[dual-machine-boundary]]"
related:
  - "[[dual-machine-boundary]]"
---

# Decision: Scope Runtime capabilities by version and channel

## Decision

Runtime capability 的主键包含 Runtime 类型、版本、接入通道和能力名；每条声明同时记录支持状态、证据等级、来源和约束。

## Rationale

OpenCode 1.18.26 同时提供本地 run、attach、HTTP server、ACP 和交互窗口。这些通道在事件粒度、审批交互和 Session 控制上不同。仅凭 `--help` 参数生成布尔 capability 会产生错误承诺。

## Consequences

- probe 的帮助输出只形成 `advertised` 证据。
- 源码、集成测试和真实运行可以逐步提高证据等级。
- Agenty 在发命令前必须按当前通道检查 capability guard。
- OpenCode 1.18.26 `cli-run-local` 不声明交互审批能力。
