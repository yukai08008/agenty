---
id: runtime-state-event-baseline
type: decision
status: draft
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

该清单目前是讨论基线而非最终协议。下一步按子状态机逐项确认，不同时扩展 Command、数据结构或实现。

## Open questions

- Turn 是否需要显式 `CANCELLING` 状态。
- Session 删除是否需要显式 `DELETING` 状态。
- 失败后的对象重试语义。
- 输出事件的最小公共集合和粒度。
