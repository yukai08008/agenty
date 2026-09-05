# v0.01 PRD — Runtime 接入基线

> 里程碑：M1 Anna
> 父版本：无 final tag；初始化基线 `main@9876fda`
> 起草日期：2026-09-05
> 类型：API 版
> 范围来源：与用户逐段讨论定稿

## 0. 一句话目标

建立独立于 AgentyMachine 的 Runtime 公共协议，并以 OpenCode 1.18.26 的无副作用探测验证第一段接入边界。

## 1. 范围

### 1.1 In-scope

- Availability、Channel、Session、Turn 四类相互独立的公共状态。
- Runtime 公共事件名称、事件外壳、标识和聚合快照。
- 需要校验、序列化或持久化的状态数据使用 Pydantic v2 BaseModel。
- 带版本、通道、证据等级和约束的 Capability 模型。
- OpenCode 1.18.26 可执行文件、版本与能力的无副作用探测。
- 公共合同测试和不调用真实模型的适配器测试。

### 1.2 Out-of-scope

- Anna 的创建和加载。
- 共享记忆、技能和根目录完整能力。
- Codex、Claude 具体实现。
- Channel 启动、连接和重连。
- 模型和 effort 的应用。
- Session 创建、恢复、导入和分叉。
- Turn 执行、审批和 JSON 事件流。
- 多 Agent 编排。
- 自研推理循环。

## 2. 不变量

- RuntimeMachine 与 AgentyMachine 独立演进，只通过命令和事件通信。
- 状态枚举与 Machine 执行器保持轻量；跨边界和可持久化状态数据使用 Pydantic v2。
- 公共模型不出现 OpenCode 专属参数名。
- 模型、effort 和 workspace 是上下文配置，不制造组合状态。
- OpenCode 默认不启用自动批准。
- 测试默认不调用真实模型。
- 运行时数据不进入 Git。

## 3. Feature 切分

### v0.01-a Runtime 公共协议

- 定义四类公共状态和标准事件名称。
- 定义 Runtime 标识、事件外壳和只读聚合快照。
- 不实现状态转移，不调用任何 Runtime。

### v0.01-b Capability 与 AvailabilityMachine

- 修正现有 Availability 状态和转移。
- 定义带版本、通道、证据和约束的 Capability 记录。
- 解决 `issue-capability-evidence-scope`。

### v0.01-c OpenCode 1.18.26 Probe

- 查找可执行文件。
- 读取版本。
- 探测带证据的能力。
- 驱动 AvailabilityMachine 并输出 RuntimeSnapshot。

每个切片单独验收，不能以“能够启动进程”代替 RuntimeMachine 完成。

## 4. 风险登记

| ID | 风险 | 严重度 | 缓解措施 | 责任人 |
|---|---|---|---|---|
| R1 | 公共协议被 OpenCode 参数污染 | high | 合同测试禁止专属字段 | Coder/Reviewer |
| R2 | 将模型、effort 等配置错误建模为状态 | medium | 状态只表达稳定生命周期 | Reviewer |
| R3 | CLI 版本变化导致能力误判 | high | probe 返回版本与证据，fixture 回归 | Coder/Tester |
| R4 | 顶层和底层重复维护同一状态 | high | 命令/事件边界和独立快照 | PM/Reviewer |

## 5. 签名

Agent-PM-v0.01
