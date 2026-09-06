# Agenty agent handoff

本文件作用于整个仓库。接手本项目的 Agent 必须先恢复状态，再开始修改。

## 1. 接手顺序

按以下顺序读取，满足任务所需后停止下钻：

1. 运行 `git status --short --branch` 和 `git log -5 --oneline`，Git 事实优先于文档。
2. 阅读 `pm-state.md`，确认里程碑、版本、功能分支和当前焦点。
3. 阅读 `dev_plans/v0.03-v0.05/PRD.md`、`TASK_CARD.yaml` 和 `TEST_CASES.md`。
4. 架构任务先读 `vault/00-index/home.md`，再按链接读取相关 summary/detail；不要一次加载整个 Vault。
5. Runtime 任务必须先运行 `<runtime> --version`；所有结论都与 `runtime + exact version + channel` 一起表达。

长期项目管理遵循：

- `/Users/andy/mycode/andy_skills/pm-project-management/SKILL.md`
- `/Users/andy/mycode/andy_skills/relational-knowledge-vault/SKILL.md`

## 2. 用户目标与产品结构

目标不是包装一个聊天 CLI，而是建立真正具有推理和记忆能力的 Agenty。初期借用 OpenCode、Codex CLI、Claude 等 Runtime，但 Agenty 与 Runtime 必须是相互独立的状态机。

目标目录是总分层级：

```text
agenty/
├── 配置与基础组件
├── Runtime 公共协议与 Adapter
├── MEMORY.md
├── memory/                 # 共享记忆
├── skills/                 # 共享技能
└── agents/
    └── anna/
        └── AGENTS.md       # Anna 的局部约束与上下文
```

根级通用部分约束所有 Agent；载入 Anna 时，再叠加 `agents/anna/AGENTS.md`。这些产品目录尚未完整实现，不要在未规划版本中提前一次性搭建。

首个里程碑是 `M1 Anna`。里程碑大于版本，需要若干版本逐步完成，不能把“创建 Anna”压成一个版本。

## 3. 不可破坏的架构约束

- `AgentyMachine` 管理 Agent 身份、目标、记忆、策略和顶层生命周期。
- `RuntimeMachine` 管理底层 Runtime 的类型/版本、事件、Session、模型、交互、监控和结果。
- 两者只通过公共命令、事件、Snapshot 和 Result 协作，不共享内部状态。
- 公共协议不能出现 OpenCode、Codex、Claude 专属字段；厂商语义只能存在于版本固定的 Adapter/Normalizer。
- 跨边界或可持久化的数据使用 Pydantic v2；Machine 本身保持普通 Python 对象。
- Runtime Session 接续必须同时锁定精确 Runtime identity、Session lineage 和 `ProjectEnvironment`，不能只凭原生 Session ID。
- 模型选择必须经过版本绑定目录校验；`desired` 与有执行证据的 `effective` 分开保存。
- 原生 Session fork 不等于 Agenty 执行分支。完整分支未来还要表达 `Env → Action(strategy) → Env' → Reward`。
- raw 厂商事件只作为诊断证据；应用消费连续、有上下文锁定的公共事件。
- auto 默认关闭。真实模型测试默认跳过，必须由显式环境变量开启。

## 4. 当前进度快照

截至 2026-09-06：

- 里程碑：`M1 Anna`，状态 `ACTIVE`。
- 当前大版本：`v0.05 RuntimeMachine 应用侧完整职责`，状态 `ACTIVE`。
- 当前分支：`v0.05-d`。
- v0.05-d 实现提交：`732df2f feat: validate runtime model and effort selection`；最新 HEAD 以 Git 为准。
- 首个 Runtime：OpenCode `1.18.26`，当前通道 `transient_process`。
- 自动回归：`125 passed, 1 skipped`。
- v0.05-a：Runtime 类型与精确版本选择，完成。
- v0.05-b：事件归一化与公共 EventStream，完成。
- v0.05-c：Session new/resume 与 ProjectEnvironment binding，完成。
- v0.05-d：模型目录、模型/effort 校验、desired/effective，完成。
- v0.05-e：交互管理，尚未开始。
- v0.05-f：监控与结果，尚未开始。

v0.05-d 的本机无模型调用探测从 OpenCode 1.18.26 得到 160 个动态目录项。该数量不是稳定协议事实；重新接手时应重新探测，不能硬编码。

## 5. 当前代码地图

| 主题 | 入口 |
|---|---|
| 公共状态、事件、Pydantic 协议 | `src/agenty/runtime/protocol.py` |
| Runtime 可用性 | `src/agenty/runtime/availability.py`, `machine.py` |
| Runtime 类型与版本选择 | `src/agenty/runtime/selection.py` |
| 公共事件流 | `src/agenty/runtime/events.py` |
| Session 与 Environment binding | `src/agenty/runtime/session.py` |
| 模型与 effort 选择 | `src/agenty/runtime/model_selection.py` |
| Turn 生命周期与执行编排 | `src/agenty/runtime/turn.py`, `runner.py` |
| OpenCode 1.18.26 Adapter | `src/agenty/runtime/opencode.py` |
| OpenCode 事件与模型目录解析 | `opencode_events.py`, `opencode_models.py` |
| 累计回归范围 | `dev_plans/v0.03-v0.05/TEST_CASES.md` |
| 应用侧六类职责 | `docs/runtime-machine-application-contract.md` |

## 6. 下一阶段：v0.05-e

不要直接把 `--auto` 加进命令。先在 `v0.05-e` 独立分支设计 Runtime 中立交互协议，再实现 OpenCode 1.18.26 映射。

必须覆盖：

- `ask / auto_approve / auto_reject / deny_by_default` 的明确策略；默认 `deny_by_default`。
- 通道 capability guard：OpenCode `cli-run-local` 不能中途把授权问题交回 Agenty，不能宣称支持 interactive approval。
- 能暂停/恢复的 Runtime 通道才允许 `WAITING_APPROVAL`。
- approve/reject 必须绑定 request ID、Turn、Session、Runtime 和决策主体。
- 自动及人工决策都产生审计事件。
- cancel/timeout 必须回收执行资源并达到明确终态。
- IN-01 至 IN-07 回归完成后，重跑 RT、EV、SE、MO 全部累计测试。

每个功能分支完成后先更新文档并停下，让用户在 IPython 中验收；不要自动进入下一功能分支。

## 7. 开发与质量门

常用命令：

```bash
cd /Users/andy/mycode/agenty
uv run pytest -q
uv run python -m compileall -q src tests
git diff --check
test "$(git ls-files data/ | wc -l | tr -d ' ')" = 0
uv run python /Users/andy/mycode/andy_skills/relational-knowledge-vault/scripts/vault_tool.py check --strict vault
```

修改 Vault 后先重新生成索引：

```bash
uv run python /Users/andy/mycode/andy_skills/relational-knowledge-vault/scripts/vault_tool.py index vault
```

本阶段涉及文件可以用 `uvx ruff check <files...>` 检查。全项目仍有早期代码遗留的 lint 基线，不要借功能任务批量改写无关文件。

真实 OpenCode 模型测试必须显式开启：

```bash
AGENTY_LIVE_OPENCODE=1 uv run pytest tests/test_opencode_live.py -q
```

这会访问外部模型并可能受到免费额度或限流影响；默认测试不得调用它。

## 8. Git 与工作区安全

- 保留用户未提交的修改，不得用 `reset --hard`、`checkout --` 或未经确认的 stash 清理。
- 本文件创建时，`pyproject.toml` 与 `uv.lock` 有用户添加 IPython 产生的未提交修改。接手时重新检查；若仍存在，不得擅自回退或夹带进功能提交。
- 新功能从上一功能分支的最新 HEAD 创建独立分支。v0.05-e 应从完成交接文档后的 `v0.05-d` 继续。
- 未经用户明确授权，不 push、不 merge、不打 tag。
- 提交前显式列出要暂存的文件，避免纳入用户改动。
- 文档中的状态若与 Git 不一致，以 Git 为准，并立即校正 `pm-state.md`。

## 9. 交接完成标准

完成一个阶段时必须同时满足：

1. 实现与自动回归完成；
2. 三件套、`pm-state.md` 和相关 Vault 决策已更新；
3. 默认测试不访问真实模型；
4. 给出可复制的 IPython 验收代码；
5. 明确哪些能力已验证、哪些只是 advertised/probe evidence；
6. 保留所有用户工作区改动；
7. 停在当前分支等待用户确认。
