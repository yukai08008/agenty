# v0.05 PRD — RuntimeMachine 应用侧完整职责

> 里程碑：M1 Anna
> 父版本：v0.03 代码基线 `a035a0e`
> 起草日期：2026-09-06
> 类型：API 版
> 范围来源：用户确认的六类 RuntimeMachine 应用职责

## 0. 一句话目标

以状态机逐类实现 Runtime 类型与版本、事件归一化、会话、模型、交互、监控与结果管理，并以统一回归合同约束 OpenCode 1.18.26。

## 1. 范围与不变量

### 1.1 In-scope

- 六类职责的完整回归用例基线。
- Runtime 类型与精确版本选择及 Adapter 注册。
- 公共事件序列与厂商事件归一化边界。
- 新建与接续 Session，以及 Session + Environment 校验。
- desired/effective 模型和 effort。
- ask、auto、deny、cancel 等交互策略和授权事件。
- 执行监控、失败分类、usage、ArtifactManifest、EventLogRef 和 TurnResult。

### 1.2 Out-of-scope

- Anna 的 Agent 定义、记忆和技能加载。
- Reward 计算和推理策略优化。
- Codex、Claude 的具体 Adapter。
- Web UI。

### 1.3 不变量

- Runtime 类型与版本共同确定 Adapter 和能力证据。
- 应用只依赖公共命令、事件、快照和结果，不依赖厂商 JSON。
- Session 接续必须同时校验项目 Environment。
- auto 权限策略默认关闭，并且所有授权决策可审计。
- 跨边界和可持久化状态使用 Pydantic v2，Machine 保持普通 Python 对象。
- 默认测试不调用真实模型，live 测试必须显式开启。
- 运行时数据不进入 Git。

## 2. 状态机蓝图

见 `docs/runtime-machine-application-contract.md`。

## 3. Feature 切分

1. `v0.05-a`：Runtime 类型、版本、Adapter 注册和选择状态机。
2. `v0.05-b`：公共事件序列和版本绑定的事件归一化。
3. `v0.05-c`：Session 新建/接续及 EnvironmentBinding。
4. `v0.05-d`：ModelSelection 和 desired/effective effort。
5. `v0.05-e`：InteractionPolicy、auto 和中途授权。
6. `v0.05-f`：监控、失败分类、usage、artifacts、事件日志和结果。

## 4. 风险登记表

| ID | 风险 | 严重度 | 缓解措施 | 责任人 |
|---|---|---|---|---|
| R1 | 六类职责被实现成一个巨大组合状态枚举 | high | 每类独立状态数据，由 RuntimeMachine 聚合 | Coder/Reviewer |
| R2 | 厂商字段泄漏到应用合同 | high | 公共模型字段回归和 Adapter 边界测试 | Tester |
| R3 | Session 与项目环境错配 | high | resume 前强制 Environment identity 校验 | Coder/Reviewer |
| R4 | auto 模式无意扩大权限 | high | 默认关闭、显式策略和审计事件 | Reviewer |
| R5 | Runtime 错误丢失可恢复信息 | high | 标准失败分类保留 retryable 与安全详情 | Coder/Tester |

## 5. 签名

Agent-PM-v0.05
