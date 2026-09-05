# OpenCode Runtime 1.18.26 能力抽象

## 1. 识别信息

```text
runtime: OpenCode
version: 1.18.26
platform: macOS arm64
installation: Homebrew anomalyco/tap/opencode
executable: /opt/homebrew/bin/opencode
release: https://github.com/anomalyco/opencode/releases/tag/v1.18.26
```

本文只描述 OpenCode 1.18.26。其他版本必须重新探测和验证，不能自动继承结论。

主要证据：

- [1.18.26 `run` 命令源码](https://github.com/anomalyco/opencode/blob/v1.18.26/packages/opencode/src/cli/cmd/run.ts)
- [OpenCode CLI 文档](https://opencode.ai/docs/cli/)
- [OpenCode Server 文档](https://opencode.ai/docs/server/)
- 本机 `opencode --help` 与各子命令 `--help`

## 2. 能力域

### 2.1 Runtime 发现与维护

| 能力 | 1.18.26 表现 | 抽象 |
|---|---|---|
| 版本探测 | `opencode --version` | `runtime.probe` |
| 调试信息 | `opencode debug info/paths/config/...` | `runtime.diagnostics` |
| 升级 | `opencode upgrade [target]` | `runtime.upgrade`，非核心执行能力 |
| 卸载 | `opencode uninstall` | 管理操作，不进入普通 Agent 权限 |

### 2.2 执行通道

OpenCode 1.18.26 至少暴露五种不同通道：

| 通道 | 入口 | 生命周期 | 适合场景 |
|---|---|---|---|
| `cli-run-local` | `opencode run` | 每次命令内启动本地 in-process server | 最小非交互接入 |
| `cli-run-attached` | `opencode run --attach URL` | 连接已有 Server | 复用长期后台能力 |
| `server-http` | `opencode serve` | 长期进程，提供 OpenAPI/事件接口 | 应用级深度集成 |
| `acp` | `opencode acp` | ACP server | 标准 Agent Client 协议接入 |
| `interactive-window` | TUI / mini / attach | 长期交互窗口 | 用户直接操作 Runtime |

能力必须绑定通道。例如“OpenCode 支持审批”不等于 `cli-run-local --format json` 能把审批交给 Agenty 处理。

## 3. 配置作用域

### Runtime 级

```text
executable
transport/channel
server URL
server authentication
log level
plugin policy (--pure)
```

### Session 级

```text
session id
title
workspace/directory
OpenCode agent
fork relationship
permission rules
```

### Turn 级

```text
prompt/command
model (provider/model)
effort (--variant)
attachments (--file)
thinking visibility
```

`model` 和 `effort` 是配置值，不是 Runtime 状态。1.18.26 源码会在创建 Session 和提交 prompt 时传递 model/variant，因此公共协议需要允许明确的作用域和有效配置快照。

## 4. Session 能力

已确认命令能力：

- 不指定 Session 时由 `run` 隐式创建。
- `--session` 恢复指定 Session。
- `--continue` 选择最近的顶层 Session。
- `--fork` 在 `--session` 或 `--continue` 基础上创建分支 Session。
- `session list --format json` 列出 Session。
- `session delete` 删除 Session。
- `export --sanitize` 脱敏导出 Session。
- `import` 从 JSON 文件或分享 URL 导入 Session。

需要区分 `open`、`resume`、`fork`、`import`、`export`、`delete`，不能只用一个 `sessions=true` 表示。

## 5. `cli-run-local + json` 的真实事件语义

`opencode run --format json` 的记录包含 `type`、`timestamp`、`sessionID` 和对应的 part/error。1.18.26 源码明确发出的 JSON 类型包括：

```text
step_start
step_finish
tool_use
text
reasoning
error
```

重要限制：

- `text` 和 `reasoning` 在 part 结束后才输出，不等同于 token delta。
- `tool_use` 在工具完成或报错时输出，不能据此可靠表达 `tool.started`。
- 内部通过 `session.status == idle` 结束监听，但没有向 JSON 输出显式的 `turn.completed`。
- 适配器需要结合 JSON error、进程退出码和 EOF 推导 Turn 终态。
- 每条 JSON 都带 `sessionID`，可建立 Agenty Session 与 Runtime Session 的映射。

因此该通道应声明：

```text
structured_events: verified
event_stream: verified
token_delta_stream: unsupported/not_observed
explicit_turn_completed_event: unsupported
session_id_in_events: verified
```

## 6. 权限与交互

1.18.26 非交互 `run` 遇到 `permission.asked` 时：

- 使用 `--auto`：自动批准一次。
- 默认：自动拒绝。

该模式不会停下来等待 Agenty 决策，所以 `cli-run-local` 不应声明 `interactive_approval` 能力。要实现 Agenty 主导审批，需要继续研究 `server-http`、ACP 或交互通道。

`--auto` 是高风险选项，Agenty 默认禁止使用；未来只能由显式权限策略开启。

## 7. Agent、Skill 与 MCP

OpenCode 自身也有 Agent、Skill 和 MCP 概念，包括 `opencode agent`、`--agent`、`opencode debug skill` 和 `opencode mcp`。

这些属于 Runtime 内部资源。Agenty 的 Anna、共享技能和记忆不能直接等同于 OpenCode Agent/Skill：

```text
Agenty Agent（产品身份与长期状态）
    ≠ OpenCode Agent（Runtime 内部执行配置）
```

## 8. 能力证据等级

| 等级 | 含义 |
|---|---|
| `advertised` | 仅在 `--help` 或文档出现 |
| `source_confirmed` | 在对应版本源码中确认 |
| `probe_verified` | 本机无副作用探测通过 |
| `integration_verified` | 通过假后端或协议集成测试 |
| `live_verified` | 真实模型/会话测试通过 |
| `unsupported` | 已确认该通道不支持 |
| `unknown` | 尚无足够证据 |

能力主键必须包含：

```text
(runtime_kind, runtime_version, channel, capability)
```

不能只保存 `OpenCode.supports_sessions = true`。

## 9. v0.01-c Probe 实现边界

当前 Probe 固定适配 OpenCode 1.18.26，并只执行：

```text
opencode --version
opencode run --help
```

本机实测结果为 `AVAILABLE`。从 help 发现的 model、variant、session、continue、fork、interactive、format 和 file 参数，被映射为 8 条中立 CapabilityRecord；所有记录均为：

```text
support: unknown
evidence: advertised
channel: transient_process
```

这说明 Runtime 宣传了相应入口，不代表 Agenty 已验证其调用语义。真实 Session、Turn、模型及 effort 操作留给后续版本。

## 10. v0.03-b Turn 调用适配

OpenCode Adapter 已实现新 Session 的同步 JSONL 调用：

```text
opencode run --format json --dir <working_directory> [--model ...] [--variant ...] -- <prompt>
```

边界如下：

- 同时使用进程 `cwd` 和 `--dir` 绑定工作目录。
- `--` 隔离 prompt，避免以 `--auto` 等文本开头的 prompt 被解释成 CLI 参数。
- 不传 `--auto`、`--session`、`--continue` 或 `--fork`。
- `step_start`、`step_finish`、`text`、`reasoning`、`tool_use`、`error` 被转换为公共输出事件。
- JSON error、非零退出、畸形输出和超时进入结构化失败终态。
- Session ID 从 JSON 事件建立，同一 Turn 内改变时拒绝继续。

上述结论目前属于假可执行文件集成测试，不提升为 `live_verified`。真实模型冒烟测试属于 v0.03-c，必须显式开启。
