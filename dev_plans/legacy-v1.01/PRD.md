# v1.01 PRD — 多 Agent 生命周期与可恢复状态机 POC

> 父版本：legacy `main@9876fda`（bootstrap 例外，无 `final`）
> 起草日期：2026-09-01
> 类型：API 版（奇数，不正式发布）
> 范围来源：2026-08-30 至 2026-09-01 用户对话定稿

## 0. 一句话目标

让 Agenty 在 `~/.agenty` 中可靠管理 N 个已有 Agent，并使每个 Agent 能从 claimed 状态创建通用 Worker、形成完整 agent suite、保存可恢复状态机上下文，再安全迁移为 Git 项目 Agent。

## 1. 范围与不变量

### 1.1 In-scope

- 初始化共享的 `~/.agenty` 控制面；
- 登记 N 个已有 Agent，每个 Agent 使用不可变 `agent_id`；
- 检测 Codex、OpenCode、Claude 等外部 runtime 命令并保存 profile；
- 分离生命周期、执行、任务三条状态轴；
- 用 `current.json`、`events.jsonl`、checkpoint 和 Agent 级锁保存状态机上下文；
- 从事件尾部恢复落后或缺失的当前快照；
- 为 claimed Agent 创建默认位于 `~/agents/<name>` 的 Worker 工作空间；
- 在 Worker 中创建三个文件、三个文件夹组成的 agent suite；
- 通过项目快照场景实际使用 bootstrap、memory、skill、session 和 agent log；
- 将 Worker 安全迁移到指定目录，可选择初始化 Git；
- 提供 init、runtime、claim、list、show、workspace、snapshot、checkpoint、history、start、migrate、doctor CLI；
- 支持 `AGENTY_HOME` 与 `AGENTY_AGENTS_HOME` 覆盖默认路径。

### 1.2 Out-of-scope

- Agenty 自己实现模型推理；
- daemon、trigger、消息队列和定时任务；
- Codex、OpenCode、Claude 的深度 session 协议；
- 多个 Agent 在同一 Git 项目中的 suite 布局；
- Web UI、远程控制面和账号系统；
- 删除 Agent、删除工作空间或自动删除迁移源目录；
- 将 v1.01 作为正式对外发布版本。

### 1.3 不变量

1. `~/.agenty` 属于 Agenty 控制面，不属于某个默认 Agent。
2. Agent 在 Agenty 之外已经存在；claim 只登记，不创造推理能力。
3. N 个 Agent 的元数据、状态、锁和日志必须物理隔离。
4. `agent_id` 创建后不可改变；名称和路径可以改变。
5. agent suite 位于具体 Worker 或 Git 项目中，不复制到 `~/.agenty`。
6. `~/.agenty` 只保存管理元数据、状态机上下文、checkpoint、runtime handle 和诊断日志。
7. `MEMORY.json`/`memory/` 是 Agent 知识；`state/current.json` 是 Agenty 运行状态，两者不得混用。
8. 状态更新必须加 Agent 级文件锁、递增 revision，并以事件和原子快照持久化。
9. 迁移前执行状态必须为 `IDLE`；迁移成功后保留源目录作为可恢复备份。
10. 迁移不得覆盖非空目标目录，不得执行 `git reset --hard` 或清除用户数据。
11. suite 中本地状态不得进入 Git：`user_skills/`、`memory/`、`sessions/`、`agent_log.jsonl`。
12. 新功能必须有自动化测试；本版本无 Web，因此前端 e2e 不适用。

### 1.4 与历史版本的关系

legacy `0.1.0` 只演示 uv CLI，没有多 Agent、状态机或迁移模型。此前 `docs/v1.01-poc-plan.md` 的单项目目录 POC 已被本 PRD 取代，但保留作为设计演进记录。

当前分支由 legacy `main@9876fda` 创建。由于这是第一次引入 PM 版本规范，不伪造未通过封板的 `v1.00-final`。

## 2. 顶层蓝图

```text
external agent/runtime
        │ claim
        ▼
~/.agenty/agents/<agent-id>/
        │ workspace create
        ▼
~/agents/<name>/
├── agent-suite/
└── workspace/
        │ migrate --init-git
        ▼
<target-project>/
├── .git/
├── agent-suite/
└── workspace/
```

```text
Agenty control plane                 Agent-owned workspace/project
~/.agenty/agents/<id>/               <root>/agent-suite/
├── metadata.json                    ├── AGENTS.md
├── bindings.json                    ├── MEMORY.json
├── state/current.json               ├── agent_log.jsonl
├── state/events.jsonl               ├── skills/
├── state/checkpoints/               ├── memory/
├── runtime/                         └── sessions/
└── logs/
```

## 3. Feature A — 多 Agent 控制面

### 3.1 Agenty home

默认使用 `~/.agenty`，测试和隔离环境通过 `AGENTY_HOME` 覆盖。初始化创建 config、agents、runtimes、locks 和系统 logs，目录权限为 `0700`，敏感 JSON 文件权限为 `0600`。

### 3.2 Agent identity

- 目录名使用 `agt_<uuid hex>`；
- display name 在本机范围内唯一；
- 名称可以作为 CLI selector，内部始终解析为 ID；
- claim 时要求 runtime profile 已存在或命令可发现。

### 3.3 Runtime profile

v1.01 只保存 runtime 名称和可执行命令。`start` 负责在 Agent 活动工作空间启动该命令，不绑定供应商私有参数。

## 4. Feature B — 状态机上下文

### 4.1 三条状态轴

```text
lifecycle: CLAIMED → WORKER → MIGRATING → PROJECT
execution: IDLE → STARTING → RUNNING → IDLE
                         ├→ WAITING/BLOCKED
                         └→ FAILED → IDLE
task:      NONE → ACTIVE → WAITING_INPUT → COMPLETED/FAILED/CANCELLED
```

### 4.2 事件与快照

- `events.jsonl` 每条事件包含 revision、UTC 时间、事件名、旧值、新值和完整新状态；
- 写入顺序为：持锁 → 验证转移 → append+fsync event → 原子替换 current；
- 如果进程在 event 后、current 前崩溃，读取时从最后一条带完整状态的事件恢复；
- checkpoint 保存完整状态与调用方 payload，并更新 `recovery.last_checkpoint`。

### 4.3 并发

使用每 Agent 独立的 `flock`。并发写入必须串行化，revision 不重复、不丢失。

## 5. Feature C — Worker 与 agent suite

### 5.1 Worker

默认根目录为 `~/agents/<agent-name>`，可用 `AGENTY_AGENTS_HOME` 或 `--path` 覆盖。非空路径默认拒绝，避免混入未知文件。

### 5.2 Suite

Worker 创建：

```text
agent-suite/
├── AGENTS.md
├── MEMORY.json
├── agent_log.jsonl
├── skills/
│   ├── project-snapshot/SKILL.md
│   └── user_skills/
├── memory/
└── sessions/
```

### 5.3 基础应用场景

`agenty snapshot <agent>` 完成一次最小项目体检：读取 bootstrap 和 MEMORY，执行 `project-snapshot` skill 的确定性检查，写入详细 memory、session 和语义 agent log，并更新 MEMORY 的关键事实入口。

## 6. Feature D — 安全迁移

`agenty migrate <agent> <target> --init-git`：

1. 要求 lifecycle=WORKER、execution=IDLE；
2. 拒绝相同路径、源目录子路径和非空目标；
3. 进入 MIGRATING 并保存 checkpoint；
4. 复制 Worker 根目录到目标，不移动或删除源；
5. 可选执行 `git init`；
6. 校验 suite；
7. 更新 binding；
8. 进入 PROJECT；
9. 失败则回到 WORKER，记录失败事件，目标保留供人工检查。

## 7. Feature E — 第一批 CLI

```text
agenty init
agenty runtime list
agenty claim NAME --runtime RUNTIME
agenty list
agenty show AGENT
agenty workspace create AGENT [--path PATH]
agenty snapshot AGENT
agenty checkpoint AGENT [--summary TEXT]
agenty history AGENT [--tail N]
agenty start AGENT [--dry-run]
agenty migrate AGENT TARGET [--init-git]
agenty doctor [AGENT]
```

输出面向人类，错误使用非零退出码。数据层保持独立，以便后续增加 JSON 输出。

## 8. 不变量自验

- 两个 Agent 并行 claim、checkpoint 时目录和 revision 不交叉；
- 删除 `current.json` 后可从 events 恢复；
- 非法 lifecycle/execution 转移被拒绝；
- suite 只存在于 Worker/Project 根；
- 迁移后 ID、事件历史、memory 和 sessions 连续；
- Git 只追踪 suite 定义，不追踪本地运行状态；
- `AGENTY_HOME` 测试不触碰真实 `~/.agenty`。

## 9. 风险登记表

| ID | 风险 | 严重度 | 缓解措施 | 责任人 |
| --- | --- | --- | --- | --- |
| R1 | 状态事件与快照因崩溃不一致 | high | event-first、fsync、原子快照、读取恢复测试 | Coder |
| R2 | 并发 CLI 造成 revision 丢失 | high | Agent 级 flock 与并发回归 | Coder/Tester |
| R3 | 迁移覆盖或删除用户文件 | high | 非空目标拒绝、源目录保留、无自动清理 | Coder/Tester |
| R4 | 外部 runtime CLI 参数不兼容 | medium | v1.01 仅启动 profile 命令，不假设私有参数 | Coder |
| R5 | 控制面与 suite 职责再次混淆 | high | 代码模块分层、vault 决策与边界测试 | PM/Reviewer |
| R6 | `v1.01` 与 PEP 440 版本冲突 | medium | v1.01 不发布，Python 包暂不改版 | PM |
| R7 | 同项目多 Agent suite 未定义 | medium | 明确 out-of-scope，不在本版暗示结论 | PM |

## 10. 签名

签名：Agent-PM-1.01
