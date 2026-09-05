---
id: agenty-state-machines
type: summary
status: active
updated: 2026-09-05
tags: [agenty, state-machine, runtime]
related:
  - "[[dual-machine-boundary]]"
  - "[[runtime-state-event-baseline]]"
---

# Agenty State Machines

## Summary

AgentyMachine 和 RuntimeMachine 是两个独立状态机。前者管理 Agent 的设计、上下文和任务，后者管理具体执行环境的配置、会话和执行；双方只通过公共命令与事件协作。

## Current state

- M1 目标是创建第一个可运行 Agent Anna。
- v0.01 已完成 RuntimeMachine 与 OpenCode 无副作用探测：本机 OpenCode 1.18.26 进入 READY，并报告 8 项可验证能力。
- 第一次顶层校准确定 AgentyMachine 使用 `RESOLVING_RUNTIME` 消费公共 RuntimeSnapshot，并通过 capability 守卫接受或阻断。
- OpenCode 1.18.26 的能力分析表明 RuntimeMachine 应聚合 Availability、Channel、Session、Turn 四个状态机；能力必须绑定版本、通道和证据等级。
- v0.01-a 已把 Runtime 状态与事件基线落成中立公共协议；四类状态独立，事件带关联上下文，快照只读聚合，尚未实现运行行为。
- 顶层和底层采用交替设计，在 Anna 完整执行链路处交汇。

## Details

- [[dual-machine-boundary]]
- [[runtime-capability-scope]]
- [[runtime-state-event-baseline]]
