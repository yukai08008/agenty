# Runtime Machine 设计草案

## 1. 分层

RuntimeMachine 不是单一的 `start()` 函数，而是三个关联生命周期。

### Runtime 生命周期

```text
UNKNOWN --probe--> PROBING
PROBING --available--> READY
PROBING --unavailable--> UNAVAILABLE
READY --fault--> DEGRADED
DEGRADED --probe--> PROBING
READY/UNAVAILABLE/DEGRADED --close--> CLOSED
```

### Session 生命周期

```text
NONE --open--> OPENING
OPENING --opened--> READY
READY --execute--> RUNNING
RUNNING --completed--> READY
RUNNING --input_required--> WAITING_INPUT
RUNNING --approval_required--> WAITING_APPROVAL
WAITING_INPUT --input_received--> RUNNING
WAITING_APPROVAL --approved--> RUNNING
READY --close--> CLOSING --closed--> CLOSED
```

失败、超时和中断在实现时根据 Runtime 能力补充，但必须保留结构化事件。

## 2. 公共数据

```text
RuntimeInfo
  id, kind, version, executable, capabilities

RuntimeConfig
  model, effort, workspace, permission_policy

SessionSpec
  title, existing_session_id, fork, interactive

ExecutionRequest
  prompt, context_files, attachments, correlation_id

RuntimeEvent
  type, runtime_id, session_id, run_id, correlation_id,
  timestamp, payload
```

Runtime 专属选项保存在适配器自己的配置区，不污染公共请求。

## 3. OpenCode 映射起点

当前本机 OpenCode `1.18.26` 提供：

- `opencode run --format json`
- `--model`、`--variant`
- `--session`、`--continue`、`--fork`
- `--dir`、`--file`
- `--interactive`
- `--attach`
- `opencode serve`、`opencode acp`

第一切片只做 `probe`：发现可执行文件、读取版本、提取可验证能力并进入 `READY` 或 `UNAVAILABLE`。它不调用模型、不创建会话。

后续切片再依次增加配置、会话和执行，避免一次实现掩盖协议边界。

## 4. 不变量

- 默认不启用自动批准。
- RuntimeMachine 不能修改 AgentyMachine 状态，只能发布事件。
- AgentyMachine 不能读取适配器私有进程对象。
- 模型和 effort 是配置，不是状态枚举。
- 探测不调用模型、不消耗额度。
- 所有外部输出在进入公共事件前必须解析和归一化。
