# Agenty 双状态机架构

## 1. 核心决定

Agenty 与 Runtime 是两个独立状态机，通过稳定协议协作。

- `AgentyMachine` 管理“Agent 是什么、要做什么”：设计、层级上下文、记忆、技能、任务和结果。
- `RuntimeMachine` 管理“任务如何在执行环境中运行”：可用性、配置、模型、effort、会话、窗口、执行、交互和故障。

两者不能合并成一个大状态机，也不能让 Agenty 直接依赖 OpenCode/Codex/Claude 的内部状态。

```text
应用 ↔ AgentyMachine ↔ Runtime Protocol ↔ RuntimeMachine
                                         ├── OpenCode
                                         ├── Codex
                                         └── Claude
```

## 2. 状态层级

### 2.1 AgentyMachine

AgentyMachine 后续负责：

```text
加载全局设计
→ 加载具体 Agent
→ 准备任务
→ 调度 Runtime
→ 等待 Runtime
→ 整理结果
→ 更新记忆
```

它只观察 Runtime 的公共事件，不复制 Runtime 的内部状态。

### 2.2 RuntimeMachine

RuntimeMachine 自身采用层级结构：

```text
Runtime lifecycle
└── Session lifecycle
    └── Turn / execution lifecycle
```

模型、effort、工作目录和 Runtime 类型属于上下文配置；改变它们是事件或命令，不为每个取值创建状态。

## 3. 协作边界

Agenty 向 Runtime 发送公共命令：

```text
probe
configure
open_session
resume_session
fork_session
execute
send_input
approve / reject
interrupt
close_session
shutdown
```

Runtime 向 Agenty 发布公共事件：

```text
runtime.available / unavailable / degraded
runtime.configured
session.opened / ready / closed
execution.started / output / completed / failed
interaction.input_required / approval_required
execution.interrupted / timeout
```

命令和事件使用 `runtime_id`、`session_id`、`run_id`、`correlation_id` 建立关联。双方分别持久化自己的状态快照，不共享可变内部对象。

## 4. 能力协商

统一协议不抹平不同 Runtime 的差异。每个 RuntimeMachine 报告能力，例如：

```text
models
effort_levels
sessions
resume
fork
interactive_window
streaming
attachments
approvals
interrupt
structured_output
```

Agenty 根据能力决定能否发送命令；能力不足时得到明确拒绝，不能静默降级。

## 5. 首个实现

OpenCode 是首个 RuntimeMachine 实现。先验证探测、能力、配置、会话和执行事件，再反向校准 AgentyMachine 所需的公共协议。

Codex 和 Claude 暂不实现，但公共模型不能使用 OpenCode 专属字段。
