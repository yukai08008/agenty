# Agenty repository instructions

本文件作用于整个仓库，定义接手方式和不可破坏的工程约束。产品目标不在这里重复维护。

## 1. 接手顺序

1. 运行 `git status --short --branch` 和 `git log -5 --oneline`；Git 事实优先于文档。
2. 阅读 `pm-state.md`，确认当前里程碑、版本、分支、工作区和下一步。
3. 阅读 `ROADMAP.md`，确认产品目标、M1 Anna 完成定义和阶段依赖。
4. 阅读 `CHANGELOG.md`，确认已经做过的行为变化、证据和限制。
5. 阅读当前版本的 `dev_plans/*/{PRD.md,TASK_CARD.yaml,TEST_CASES.md}`。
6. 架构任务从 `vault/00-index/home.md` 按关系逐层读取；不要一次加载整个 Vault。
7. Runtime 任务先运行 `<runtime> --version`；所有结论必须绑定 Runtime 类型、精确版本和 Channel。

项目管理与知识库遵循：

- `/Users/andy/mycode/andy_skills/pm-project-management/SKILL.md`
- `/Users/andy/mycode/andy_skills/relational-knowledge-vault/SKILL.md`

## 2. 文档职责

| 文件 | 唯一职责 |
|---|---|
| `AGENTS.md` | Agent 如何接手与工作 |
| `ROADMAP.md` | 项目最终要做到什么、按什么顺序推进 |
| `pm-state.md` | 当前做到哪里、下一步是什么 |
| `CHANGELOG.md` | 曾经做过什么、验证与限制是什么 |
| `dev_plans/` | 具体版本范围、任务卡和验收用例 |
| `vault/` | 架构决策、运行知识与主题关系 |

不要在多个文件复制同一份动态状态。文档与 Git 不一致时，以 Git 为准并校正文档。

## 3. 工程不变量

- `AgentyMachine` 管理 Agent 身份、目标、记忆、策略和顶层生命周期。
- `RuntimeMachine` 管理 Runtime 类型/版本、事件、Session、模型、交互、监控和结果。
- 两者只通过公共命令、事件、Snapshot 和 Result 协作，不共享内部状态。
- 公共协议不能出现 OpenCode、Codex、Claude 专属字段；厂商语义只能存在于版本固定的 Adapter/Normalizer。
- 跨边界或可持久化的数据使用 Pydantic v2；Machine 保持普通 Python 对象。
- Runtime Session 接续必须共同锁定 Runtime identity、Session lineage 和 `ProjectEnvironment`。
- 模型选择必须经过版本绑定目录校验；`desired` 与有执行证据的 `effective` 分开保存。
- 原生 Session fork 不等于 Agenty 执行分支；完整分支未来表达 `Env → Action(strategy) → Env' → Reward`。
- raw 厂商事件只作为诊断证据；应用只消费公共归一化事件。
- auto 默认关闭；真实模型测试默认跳过，必须显式开启。
- 一个里程碑由若干版本完成。未经用户确认，不提前冻结后续版本号或一次性实现未来目录。

## 4. 当前代码地图

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
| OpenCode 事件与模型目录 | `src/agenty/runtime/opencode_events.py`, `opencode_models.py` |
| RuntimeMachine 六类职责 | `docs/runtime-machine-application-contract.md` |

## 5. 开发与质量门

```bash
cd /Users/andy/mycode/agenty
uv run pytest -q
uv run python -m compileall -q src tests
git diff --check
test "$(git ls-files data/ | wc -l | tr -d ' ')" = 0
uv run python /Users/andy/mycode/andy_skills/relational-knowledge-vault/scripts/vault_tool.py check --strict vault
```

修改 Vault 后先运行索引，再做严格检查：

```bash
uv run python /Users/andy/mycode/andy_skills/relational-knowledge-vault/scripts/vault_tool.py index vault
```

本次涉及文件可用 `uvx ruff check <files...>` 检查。全项目仍有早期 lint 基线，不要借功能任务批量重写无关文件。

真实 OpenCode 模型测试必须显式开启：

```bash
AGENTY_LIVE_OPENCODE=1 uv run pytest tests/test_opencode_live.py -q
```

它会访问外部模型并可能受免费额度或限流影响；默认回归不得调用。

## 6. Git 与工作区安全

- 保留用户未提交修改；禁止 `git reset --hard`、`git checkout --` 或未经确认的 stash。
- 新功能从上一功能分支最新 HEAD 创建独立分支。
- 未经用户明确授权，不 push、不 merge、不打 tag。
- 提交前显式列出暂存文件，避免夹带用户改动。
- 运行时数据不得进入 Git。

## 7. 阶段交付

完成一个功能分支时：

1. 实现与累计自动回归完成；
2. 更新三件套、`pm-state.md`、`CHANGELOG.md` 和相关 Vault 决策；路线变化才修改 `ROADMAP.md`；
3. 明确区分 advertised、probe、integration 和 live 证据；
4. 提供可复制的 IPython 或命令行验收步骤；
5. 保留用户工作区改动；
6. 停在当前分支等待用户确认，不自动进入下一阶段。
