---
id: agenty-state-machines
type: summary
status: active
updated: 2026-09-05
tags: [agenty, state-machine, runtime]
related:
  - "[[dual-machine-boundary]]"
---

# Agenty State Machines

## Summary

AgentyMachine 和 RuntimeMachine 是两个独立状态机。前者管理 Agent 的设计、上下文和任务，后者管理具体执行环境的配置、会话和执行；双方只通过公共命令与事件协作。

## Current state

- M1 目标是创建第一个可运行 Agent Anna。
- v0.01 从 RuntimeMachine 与 OpenCode 无副作用探测开始。
- 顶层和底层采用交替设计，在 Anna 完整执行链路处交汇。

## Details

- [[dual-machine-boundary]]
