# v0.03 PRD — Runtime 最小 Turn 调用链

> 里程碑：M1 Anna
> 父版本：v0.01 代码基线 `80be93f`
> 起草日期：2026-09-06
> 类型：API 版
> 范围来源：v0.01 Probe 验收后的调用测试需求

## 0. 一句话目标

建立独立于具体 Runtime 的最小 Turn 调用协议，并以 OpenCode 1.18.26 的 JSON 输出完成可回归、可显式实测的第一条调用链。

## 1. 范围与不变量

### 1.1 In-scope

- Pydantic Turn 请求、失败和可持久化状态数据。
- 纯 TurnMachine 及标准 RuntimeEvent 转移。
- 每次调用必须指定工作目录；新建 Session 时记录 Runtime 返回的 Session ID。
- OpenCode 1.18.26 `run --format json` 的独立 Adapter。
- 假进程集成测试，以及默认不执行、必须显式开启的真实模型冒烟测试。

### 1.2 Out-of-scope

- Session 恢复、分叉和完整 ProjectEnvironment 快照。
- `Env → Action(strategy) → Env' → Reward` 的完整实现。
- 交互审批、自动批准和长期 Server/ACP 通道。
- Anna、记忆、技能和顶层完整任务循环。
- Codex 与 Claude Adapter。

### 1.3 不变量

- RuntimeMachine 与 AgentyMachine 不共享内部状态。
- 公共 Turn 模型不包含 OpenCode 专属参数。
- Machine 是普通 Python 对象；跨边界和可持久化数据使用 Pydantic v2。
- 默认不启用 `--auto`，自动测试不调用真实模型。
- 调用必须显式绑定工作目录；本版不宣称该目录等同于完整 Environment identity。
- 未实现 Environment 校验前，不开放 Session resume/fork。
- 运行时数据不进入 Git。

### 1.4 与历史版本的关系

v0.01 只确认 Runtime 可用性和 advertised 能力。v0.03 在该基线上增加 Turn 行为验证，并把成功的实际调用证据与 help 广告证据分开。

## 2. 顶层蓝图

```text
Agenty command
    │ RuntimeTurnRequest(workspace, prompt, config)
    ▼
Runtime TurnMachine
    │ normalized RuntimeEvent
    ▼
OpenCode 1.18.26 Adapter ── opencode run --format json
```

## 3. Feature 切分

### v0.03-a 公共 Turn 协议与状态机

- 定义中立的 Turn 请求与状态数据。
- 实现标准生命周期和输出事件的状态守卫。
- 校准 AgentyMachine：只有 Runtime `AVAILABLE` 且调用需求可满足时才进入下一阶段。

### v0.03-b OpenCode JSON 调用适配

- 只允许新建 Session，并显式传入工作目录。
- 将 JSONL 转换为公共事件。
- 使用输出、错误、退出码和 EOF 推导终态。
- 使用假可执行文件覆盖成功、错误、超时和畸形事件。

### v0.03-c 显式真实冒烟测试

- 默认跳过，只有显式环境开关才调用真实模型。
- 记录 Runtime 版本、工作目录、Session ID、Turn 终态和证据。
- 成功后只提升实际覆盖能力的证据，不批量提升 advertised 能力。

## 4. 风险登记表

| ID | 风险 | 严重度 | 缓解措施 | 责任人 |
|---|---|---|---|---|
| R1 | 测试意外调用模型并产生费用 | high | live 测试默认跳过并要求显式开关 | Coder/Tester |
| R2 | Session 与项目环境错配 | high | 本版只允许新 Session；请求强制工作目录 | Reviewer |
| R3 | OpenCode 私有 JSON 泄漏进公共协议 | high | Adapter 归一化合同测试 | Coder/Reviewer |
| R4 | 仅凭成功退出误判 Turn 成功 | high | 同时检查 JSON error、退出码和 EOF | Tester |

## 5. 签名

Agent-PM-v0.03
