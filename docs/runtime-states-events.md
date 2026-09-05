# RuntimeMachine 状态与事件清单

> 状态：v0.01-a 公共协议实现基线，待验收
>
> 首个校验对象：OpenCode 1.18.26
>
> 范围：只列 RuntimeMachine 的状态和事件，不展开命令、数据结构和实现。

对应代码位于 `src/agenty/runtime/protocol.py`。该模块只定义公共事实，不启动 Runtime，也不执行状态转移。

与 andybot 保持一致：状态继续使用字符串 Enum；需要校验、跨边界传输或持久化的 Identity、Event、Snapshot 和 StateData 使用 Pydantic v2 BaseModel；Machine 执行器本身保持普通 Python 对象。

RuntimeMachine 由四个相互独立、存在协作关系的子状态机组成：

```text
RuntimeMachine
├── AvailabilityMachine   Runtime 是否可用
├── ChannelMachine        与 Runtime 的通信通道
├── SessionMachine        Runtime 内部会话
└── TurnMachine           一次输入和执行
```

事件使用“已经发生的事实”命名。`probe`、`open_session`、`submit_turn`、`cancel_turn` 等请求属于 Command，暂不放入本清单。

## 1. AvailabilityMachine

### 状态

| 状态 | 含义 |
|---|---|
| `UNKNOWN` | 尚未检测 Runtime |
| `PROBING` | 正在检测程序、版本和能力 |
| `AVAILABLE` | Runtime 可用 |
| `DEGRADED` | 可以运行，但部分能力不可用或检测不完整 |
| `UNAVAILABLE` | 程序不存在或无法启动 |
| `INCOMPATIBLE` | 找到 Runtime，但版本不受支持 |
| `CLOSED` | RuntimeMachine 已关闭 |

### 事件

```text
probe_started
runtime_detected
runtime_missing
runtime_unavailable
runtime_incompatible
capabilities_resolved
capability_probe_failed
runtime_degraded
runtime_recovered
runtime_lost
runtime_closed
```

`runtime_missing` 表示找不到可执行文件；`runtime_unavailable` 表示可执行入口已解析，但探测命令无法启动、超时或非零退出。两者都进入 `UNAVAILABLE`，失败原因由结构化 `RuntimeFailure` 保留。

## 2. ChannelMachine

通道类型是配置，不是状态：

```text
transient_process
managed_server
remote_server
acp
interactive_window
```

### 状态

| 状态 | 含义 |
|---|---|
| `DETACHED` | 没有活动连接 |
| `STARTING` | 正在启动本地 Runtime 通道 |
| `CONNECTING` | 正在连接已有 Runtime 通道 |
| `CONNECTED` | 通信通道可用 |
| `DEGRADED` | 仍可通信，但能力受限 |
| `STOPPING` | 正在停止或断开 |
| `FAILED` | 建立或维持通道失败 |

### 事件

```text
channel_starting
channel_connecting
channel_connected
channel_degraded
channel_failed
channel_connection_lost
channel_stopping
channel_detached
```

Adapter 还可能观察到以下底层事件，再将其转换为标准 Channel 事件：

```text
process_started
process_exited
process_killed
```

## 3. SessionMachine

Session 是 Runtime 内部的对话历史容器，不等同于 Agenty Agent，也不等同于 Agenty 的长期记忆。

### 状态

| 状态 | 含义 |
|---|---|
| `NONE` | 尚未绑定 Runtime 会话 |
| `RESOLVING` | 正在创建、恢复或导入会话 |
| `READY` | 会话可接收新 Turn |
| `BUSY` | 当前有 Turn 正在执行 |
| `FORKING` | 正在派生新会话 |
| `CLOSING` | 正在释放会话 |
| `CLOSED` | 会话已关闭 |
| `FAILED` | 会话操作失败 |

### 事件

```text
session_resolution_started
session_resolved
session_resolution_failed
session_fork_started
session_forked
session_became_busy
session_became_ready
session_lost
session_close_started
session_closed
```

`session_resolution_started` 通过 payload 区分 `create`、`resume`、`import`，不把三种方式拆成三套状态。

## 4. TurnMachine

一次用户输入对应一个 Turn。Turn 到达终态后不复用。

### 状态

| 状态 | 含义 |
|---|---|
| `CREATED` | Turn 已建立 |
| `SUBMITTING` | 正在提交给 Runtime |
| `RUNNING` | Runtime 正在执行 |
| `WAITING_INPUT` | 等待补充输入 |
| `WAITING_APPROVAL` | 等待权限批准 |
| `SUCCEEDED` | 成功完成 |
| `FAILED` | 执行失败 |
| `CANCELLED` | 主动取消 |
| `TIMED_OUT` | 执行超时 |

### 生命周期事件

```text
turn_created
turn_submission_started
turn_accepted
turn_waiting_for_input
turn_input_supplied
turn_waiting_for_approval
turn_approval_resolved
turn_succeeded
turn_failed
turn_cancelled
turn_timed_out
```

### 输出事件

以下事件描述执行过程中产生的内容，不一定引起状态变化：

```text
step_started
step_finished
text_emitted
reasoning_emitted
tool_started
tool_completed
tool_failed
usage_reported
runtime_error_emitted
```

## 5. OpenCode 1.18.26 边界

- `WAITING_INPUT` 和 `WAITING_APPROVAL` 属于 Runtime 公共抽象，但具体通道必须通过 capability guard 才能进入。
- OpenCode 1.18.26 的 `cli-run-local --format json` 目前不能可靠地让 Agenty 接管交互审批，因此不声明该通道支持 `WAITING_APPROVAL`。
- OpenCode 原始事件必须经过 Adapter 归一化后，才能成为本清单中的公共事件。
- 如果原始通道没有提供某个事件，Adapter 不得把未经验证的推断伪装成 Runtime 原生事件。

## 6. 尚待逐项确认

- `CANCELLING` 是否需要作为 Turn 的显式过渡状态。
- 删除 Session 是否需要独立的 `DELETING` 状态，还是作为关闭原因记录。
- `FAILED` 是否允许重试，重试时复用对象还是创建新对象。
- 输出事件的最小公共集合及事件粒度。
