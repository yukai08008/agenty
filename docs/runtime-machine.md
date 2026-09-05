# Runtime Machine 设计

> 状态和事件的独立讨论基线见 [RuntimeMachine 状态与事件清单](runtime-states-events.md)。

## 1. 定位

RuntimeMachine 是一个聚合状态机。它管理某个明确的 `Runtime + 版本`，并通过具体接入通道控制配置、Session 和 Turn。

```text
RuntimeMachine
├── AvailabilityMachine   安装、版本、兼容性
├── ChannelMachine        CLI / Server / ACP / Window
├── SessionMachine        创建、恢复、分叉、关闭
└── TurnMachine           一次输入的提交、执行、交互和结果
```

采用多个有层级关系的小状态机，而不是把所有组合展开成一个巨大枚举。

## 2. 标识

Runtime 实例由以下字段共同确定：

```text
runtime_id
runtime_kind
runtime_version
channel
endpoint/process identity
```

例如：

```text
runtime_id: local-opencode
runtime_kind: opencode
runtime_version: 1.18.26
channel: cli-run-local
```

## 3. AvailabilityMachine

管理 Runtime 是否存在、版本是否可识别以及当前是否可用于继续连接。

```mermaid
stateDiagram-v2
    [*] --> UNKNOWN
    UNKNOWN --> PROBING: probe
    UNAVAILABLE --> PROBING: probe
    DEGRADED --> PROBING: probe
    AVAILABLE --> PROBING: reprobe
    PROBING --> AVAILABLE: probe_succeeded
    PROBING --> UNAVAILABLE: executable_missing
    PROBING --> INCOMPATIBLE: version_unsupported
    AVAILABLE --> DEGRADED: fault_detected
    AVAILABLE --> CLOSED: close
    UNAVAILABLE --> CLOSED: close
    INCOMPATIBLE --> CLOSED: close
    DEGRADED --> CLOSED: close
```

这里使用 `AVAILABLE`，不使用含义过宽的 `READY`。Runtime 只有可用，并不代表通道、Session 或配置已经就绪。

## 4. ChannelMachine

管理连接到 Runtime 的方式。通道模式是配置，连接情况是状态。

```text
channel mode:
  transient_process
  managed_server
  remote_server
  acp
  interactive_window
```

```mermaid
stateDiagram-v2
    [*] --> DETACHED
    DETACHED --> STARTING: start_managed
    DETACHED --> CONNECTING: connect
    STARTING --> CONNECTED: started
    CONNECTING --> CONNECTED: connected
    STARTING --> FAILED: start_failed
    CONNECTING --> FAILED: connect_failed
    CONNECTED --> DEGRADED: channel_fault
    DEGRADED --> CONNECTING: reconnect
    CONNECTED --> STOPPING: disconnect
    STOPPING --> DETACHED: stopped
```

`cli-run-local` 是 transient channel：每个 Turn 内部临时建立，Turn 结束后回收。`serve`、`attach` 和 ACP 才可能形成跨 Turn 的长期连接。

## 5. SessionMachine

Session 是 Runtime 内部的对话历史容器，不等同于 Agenty Agent。

```mermaid
stateDiagram-v2
    [*] --> NONE
    NONE --> RESOLVING: open
    NONE --> RESOLVING: resume
    NONE --> RESOLVING: import
    READY --> FORKING: fork
    RESOLVING --> READY: session_resolved
    RESOLVING --> FAILED: session_failed
    FORKING --> READY: fork_created
    FORKING --> FAILED: fork_failed
    READY --> BUSY: turn_started
    BUSY --> READY: turn_finished
    READY --> CLOSING: close
    CLOSING --> CLOSED: closed
    READY --> DELETING: delete
    DELETING --> CLOSED: deleted
```

Session 的 `READY/BUSY` 表达是否有活跃 Turn；具体执行细节由 TurnMachine 管理。

## 6. TurnMachine

一个用户输入产生一个独立 Turn。Turn 有自己的终态，不在完成后复用同一个状态对象。

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> SUBMITTING: execute
    SUBMITTING --> RUNNING: accepted
    SUBMITTING --> FAILED: rejected
    RUNNING --> WAITING_INPUT: input_required
    RUNNING --> WAITING_APPROVAL: approval_required
    WAITING_INPUT --> RUNNING: input_supplied
    WAITING_APPROVAL --> RUNNING: approved
    WAITING_APPROVAL --> RUNNING: rejected
    RUNNING --> SUCCEEDED: completed
    RUNNING --> FAILED: execution_failed
    RUNNING --> CANCELLING: cancel
    CANCELLING --> CANCELLED: cancelled
    RUNNING --> TIMED_OUT: timeout
```

并非每个通道都支持 `WAITING_INPUT/WAITING_APPROVAL`。状态图表达公共上限，具体通道通过 capability guard 决定转移是否合法。

对 OpenCode 1.18.26 `cli-run-local --format json`：

- 支持 `CREATED → SUBMITTING → RUNNING`。
- 成功终态需要从进程成功退出和 JSON 无 error 推导。
- 当前不支持进入 `WAITING_APPROVAL`，因为权限请求会被 CLI 自动拒绝或在 `--auto` 下自动批准。

## 7. 配置作用域

配置必须有作用域，不能全部塞进 Runtime 全局状态：

```text
RuntimeProfile
  executable, channel, endpoint, authentication, plugin_policy

SessionConfig
  workspace, title, runtime_agent, permission_policy

TurnConfig
  model, effort, prompt, attachments, show_reasoning
```

RuntimeMachine 保存 `desired_config` 和 `effective_config`。应用配置变更时先验证 capability，再在合适边界生效；不能仅因字段写入成功就宣称已经切换。

## 8. 公共命令

```text
probe_runtime
open_channel / close_channel
open_session / resume_session / fork_session
submit_turn
supply_input
reply_approval
cancel_turn
close_session / delete_session
close_runtime
```

## 9. 公共事件

```text
runtime.probing / available / unavailable / incompatible / degraded
channel.starting / connected / failed / detached
session.resolving / ready / busy / failed / closed
turn.submitting / running / output / waiting_input / waiting_approval
turn.succeeded / failed / cancelling / cancelled / timed_out
```

所有事件包含：

```text
runtime_id
runtime_kind
runtime_version
channel
session_id（适用时）
turn_id（适用时）
correlation_id
timestamp
payload
raw_event（可选，诊断用途）
```

## 10. 能力模型

能力记录不是布尔集合，而是带作用域和证据的声明：

```text
RuntimeCapabilityRecord
  capability
  channel
  support_status
  evidence_level
  evidence_source
  constraints
```

例如：

```text
capability: interactive_approval
runtime: opencode@1.18.26
channel: cli-run-local
support_status: unsupported
evidence_level: source_confirmed
constraint: permission requests are auto-rejected unless --auto
```

## 11. 当前实现与设计差距

现有 probe 代码只返回 capability 名称集合，会把“帮助中存在某参数”误当成“行为已验证”。下一实现切片需要：

1. 将 `READY` 更名或迁移为 `AVAILABLE`。
2. 增加 `INCOMPATIBLE`。
3. 把能力改成带版本、通道、证据等级和约束的记录。
4. 不再仅凭 `--interactive` 参数声明交互窗口已验证。
5. 在完成以上校正后，才进入模型/effort 配置和 Session 实现。

## 12. 不变量

- RuntimeMachine 不能修改 AgentyMachine 状态，只发布公共事件。
- AgentyMachine 不能读取 Runtime 适配器的进程或连接对象。
- 能力必须绑定 Runtime、版本和通道。
- 模型与 effort 是配置，不是状态。
- 默认不启用自动批准。
- 原始事件必须先归一化，才能影响公共状态。
