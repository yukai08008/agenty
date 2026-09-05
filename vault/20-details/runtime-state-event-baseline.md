---
id: runtime-state-event-baseline
type: decision
status: active
updated: 2026-09-05
tags: [agenty, runtime, state-machine, events]
part_of:
  - "[[agenty-state-machines]]"
depends_on:
  - "[[dual-machine-boundary]]"
related:
  - "[[runtime-capability-scope]]"
---

# Runtime state and event baseline

## Current baseline

RuntimeMachine 暂按 Availability、Channel、Session、Turn 四个子状态机讨论。状态与事件清单的项目文档是 `docs/runtime-states-events.md`。

v0.01-a 已将该清单实现为 `src/agenty/runtime/protocol.py`：四类状态保持独立，标准事件通过 RuntimeEvent 携带 Runtime、correlation、Session 和 Turn 上下文，RuntimeSnapshot 只做只读聚合。v0.01-b 根据 andybot 约束将跨边界协议模型迁移为 Pydantic v2。

该基线仍可在版本内调整。v0.01-b 实现 Availability 状态转移和 Capability；v0.01-c 实现通用 Probe 编排与 OpenCode 1.18.26 无副作用 Adapter，并将失败上下文写入 RuntimeSnapshot。Channel、Session 和 Turn 行为仍未实现。

## Open questions

- Turn 是否需要显式 `CANCELLING` 状态。
- Session 删除是否需要显式 `DELETING` 状态。
- 失败后的对象重试语义。
- 输出事件的最小公共集合和粒度。
