---
id: runtime-application-contract
type: decision
status: active
updated: 2026-09-06
tags: [agenty, runtime, application-contract, state-machine]
part_of:
  - "[[agenty-state-machines]]"
depends_on:
  - "[[dual-machine-boundary]]"
  - "[[runtime-state-event-baseline]]"
related:
  - "[[runtime-capability-scope]]"
  - "[[runtime-turn-contract]]"
---

# Decision: RuntimeMachine exposes six application-facing responsibilities

## Decision

RuntimeMachine 对应用统一负责六类底层 Runtime 对接和管理：Runtime 类型与版本、事件归一化、会话管理、模型与 effort、交互管理、执行监控与结果管理。应用只依赖公共命令、事件、快照和结果。

## Regression baseline

v0.05 已在 `dev_plans/v0.03-v0.05/TEST_CASES.md` 为六类职责建立累计回归清单，按 a 到 f 逐类实现。后续每个 Runtime 与版本都必须重跑适用的公共合同。

## Current implementation

v0.05-a 已实现精确 `RuntimeTarget(kind, version)`、RuntimeAdapterRegistry 和 RuntimeSelectionMachine。未注册版本不回退；Adapter 身份与目标不一致时拒绝选择；状态和事件使用 Pydantic 模型并可持久化恢复。本机 OpenCode 1.18.26 已通过该选择机真实进入 `SELECTED`。

v0.05-b 已实现 RuntimeEventStreamMachine 与 OpenCode 1.18.26 EventNormalizer。EventStream 分配连续 sequence 并锁定关联上下文；公共事件与 raw 诊断数据分离。EV-01 至 EV-06 已自动化。

v0.05-c 已实现 ProjectEnvironment、RuntimeSessionBinding、SessionMachine 和 binding catalog。resume 必须同时匹配精确 Runtime identity、Session ID 与完整 Environment；校验成功后 OpenCode Adapter 才使用 `--session`，并拒绝返回其他 Session ID。原生 `--continue`/`--fork` 不承担这一应用语义。

v0.05-d 已实现 RuntimeModelSelectionMachine 和版本绑定的模型目录。模型类型/provider/model ID 与 effort 使用中立模型；未知模型、非法 effort 和 Runtime 错配在 Turn 前失败。desired 不被 Runtime 实际值覆盖，effective 只接受 integration/live 执行证据。OpenCode 1.18.26 使用 `models --verbose` 探测并映射 `--model`/`--variant`。

v0.05-e 已实现 RuntimeInteractionMachine 和授权审计。RuntimeTurnRequest 默认 deny_by_default；ask 使用 request ID 暂停和恢复 Turn，自动及人工决定只在 Adapter 接收成功后记录 actor、时间和结果，等待审批有独立超时。OpenCode 1.18.26 transient_process 的 `--auto` 只由显式 auto_approve 映射；该 Channel 没有审批回复控制面，因此 ask 在启动前拒绝，cancel 由 Adapter 回收进程组。
