# v0.01 PRD — Runtime Machine 与 OpenCode 底层适配

> 里程碑：M1 Anna
> 父版本：无 final tag；初始化基线 `main@9876fda`
> 起草日期：2026-09-05
> 类型：API 版
> 范围来源：与用户逐段讨论定稿

## 0. 一句话目标

建立独立于 AgentyMachine 的 RuntimeMachine 公共模型，并以 OpenCode 为例从无副作用探测开始逐步验证协议。

## 1. 范围

### 1.1 In-scope

- Runtime、Session、Execution 三层生命周期模型。
- 公共命令、事件、能力和错误模型。
- OpenCode 可执行文件、版本与能力探测。
- OpenCode 配置、会话和 JSON 执行的后续切片设计。
- 公共合同测试和不调用真实模型的适配器测试。
- 每完成一个底层切片，回到 AgentyMachine 做协议校准。

### 1.2 Out-of-scope

- Anna 的创建和加载。
- 共享记忆、技能和根目录完整能力。
- Codex、Claude 具体实现。
- 多 Agent 编排。
- 自研推理循环。

## 2. 不变量

- RuntimeMachine 与 AgentyMachine 独立演进，只通过命令和事件通信。
- 公共模型不出现 OpenCode 专属参数名。
- 模型、effort 和 workspace 是上下文配置，不制造组合状态。
- OpenCode 默认不启用自动批准。
- 测试默认不调用真实模型。
- 运行时数据不进入 Git。

## 3. 交付切片

### A. Runtime 公共模型

- 定义状态、事件、能力、错误和关联 ID。
- 定义 RuntimeAdapter 最小协议。

### B. OpenCode Probe

- 查找可执行文件。
- 读取版本。
- 探测或声明可验证能力。
- 驱动 `UNKNOWN → PROBING → READY/UNAVAILABLE`。

### C. 顶层协议校准

- 用 probe 结果验证 AgentyMachine 如何选择 Runtime、等待和处理不可用。
- 只调整协议，不实现完整 AgentyMachine。

### D. 后续底层切片

- 配置模型和 effort。
- 打开、恢复、分叉会话。
- 执行并归一化 JSON 事件。
- 中断、超时、审批和关闭。

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
