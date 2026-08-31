# Agenty

[English](README.md)

Agenty 用于管理 N 个外部 Agent 的生命周期和可恢复状态。推理与执行能力依托 Codex、OpenCode、Claude 等 runtime，Agenty 不重复实现模型 Agent。

v1.01 POC 覆盖三个阶段：

```text
CLAIMED → WORKER → MIGRATING → PROJECT
```

- `CLAIMED`：将已经存在的 Agent 登记到共享的 `~/.agenty` 控制面。
- `WORKER`：为 Agent 创建通用工作空间，默认位于 `~/agents/<name>`。
- `PROJECT`：保持同一个 Agent ID 和 suite，将 Worker 安全迁移为 Git 项目 Agent。

## 安装

```bash
curl -fsSL https://raw.githubusercontent.com/yukai08008/agenty/main/install.sh | bash
```

或使用 uv：

```bash
uv tool install git+https://github.com/yukai08008/agenty.git
```

## 快速开始

```bash
# 初始化共享的多 Agent 控制面
agenty init

# 查看检测到的 runtime；也可以显式添加
agenty runtime list
agenty runtime add local-codex -- /absolute/path/to/codex

# 登记两个已经存在的 Agent
agenty claim research-worker --runtime local-codex
agenty claim maintenance-worker --runtime local-codex
agenty list

# 创建通用 Worker，并实际使用完整 agent suite
agenty workspace create research-worker
agenty snapshot research-worker
agenty checkpoint research-worker --summary "ready for project migration"

# 预览 runtime 启动
agenty start research-worker --dry-run

# 迁移为 Git 项目；迁移后源 Worker 目录仍保留
agenty migrate research-worker ~/mycode/research-project --init-git
agenty doctor research-worker
```

## 存储边界

共享控制面只保存每个 Agent 的少量运行信息：

```text
~/.agenty/
├── agents/<agent-id>/
│   ├── metadata.json
│   ├── bindings.json
│   ├── state/current.json
│   ├── state/events.jsonl
│   ├── state/checkpoints/
│   ├── runtime/
│   └── logs/
├── runtimes/
├── locks/
└── logs/
```

Agent 的身份引导、知识、技能、会话和语义操作记录位于 Worker 或项目中：

```text
<agent-root>/
├── AGENTS.md -> agent-suite/AGENTS.md
├── agent-suite/
│   ├── AGENTS.md
│   ├── MEMORY.json
│   ├── agent_log.jsonl
│   ├── skills/
│   ├── memory/
│   └── sessions/
└── workspace/
```

可使用 `AGENTY_HOME` 和 `AGENTY_AGENTS_HOME` 覆盖默认路径。测试始终使用临时隔离目录，不会触碰用户真实控制面。

## 状态恢复

每个 Agent 分别维护 lifecycle、execution 和 task 三条状态轴。每次更新都会获取 Agent 级文件锁、递增 revision、追加包含完整状态的 JSONL 事件，再原子替换当前快照。如果进程在事件写入后停止，Agenty 会从事件日志恢复 `current.json`。

## 开发

```bash
uv run python -m unittest discover -s tests -v
uv build
```

当前状态见 `pm-state.md`，v1.01 的 PRD、任务卡和测试设计位于 `dev_plans/legacy-v1.01/`。

## 卸载

```bash
curl -fsSL https://raw.githubusercontent.com/yukai08008/agenty/main/install.sh | bash -s -- uninstall
```
