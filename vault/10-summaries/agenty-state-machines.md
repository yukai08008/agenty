---
id: agenty-state-machines
type: summary
status: active
updated: 2026-09-05
tags: [agenty, state-machine, runtime]
related:
  - "[[dual-machine-boundary]]"
  - "[[runtime-state-event-baseline]]"
  - "[[execution-branch-context]]"
---

# Agenty State Machines

## Summary

AgentyMachine 和 RuntimeMachine 是两个独立状态机。前者管理 Agent 的设计、上下文和任务，后者管理具体执行环境的配置、会话和执行；双方只通过公共命令与事件协作。

## Current state

- M1 目标是创建第一个可运行 Agent Anna。
- v0.01-c 已将 OpenCode Probe 迁移到公共 AvailabilityMachine：通用编排与版本绑定 Adapter 分离，失败结构化，help 参数只形成 `unknown/advertised` 能力记录。本机 OpenCode 1.18.26 无模型探测结果为 `AVAILABLE`。
- v0.03-a 已实现公共 TurnMachine：每个请求显式绑定工作目录、Turn 和 correlation，上下文不匹配时拒绝事件；工作目录不等同于完整 Environment，Session resume/fork 仍被排除。
- v0.03-b 已实现 OpenCode 1.18.26 JSONL 调用适配和通用 Runner；假进程调用链已覆盖成功与主要失败路径，真实模型测试仍需显式开启。
- 第一次顶层校准确定 AgentyMachine 使用 `RESOLVING_RUNTIME` 消费公共 RuntimeSnapshot，并通过 capability 守卫接受或阻断。
- OpenCode 1.18.26 的能力分析表明 RuntimeMachine 应聚合 Availability、Channel、Session、Turn 四个状态机；能力必须绑定版本、通道和证据等级。
- v0.01-a 已把 Runtime 状态与事件基线落成中立公共协议；四类状态独立，事件带关联上下文，快照只读聚合，尚未实现运行行为。
- v0.01-b 已实现带版本、Channel、支持状态、证据和约束的 CapabilityRecord，以及由标准事件驱动的 AvailabilityMachine。对齐 andybot：状态枚举使用 Enum，跨边界和可持久化状态数据使用 Pydantic v2，Machine 保持普通 Python 对象。
- 执行分支必须同时绑定 Runtime Session lineage 与项目 Environment；Env、Action/Strategy、Reward 是后续设计的一等概念，原生 Session fork 不能单独承担该语义。
- 顶层和底层采用交替设计，在 Anna 完整执行链路处交汇。

## Details

- [[dual-machine-boundary]]
- [[runtime-capability-scope]]
- [[runtime-state-event-baseline]]
- [[execution-branch-context]]
- [[runtime-turn-contract]]
