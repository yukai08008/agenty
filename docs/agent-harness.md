# Agent Harness 设计

> 状态：`PROPOSED`
> 适用范围：Agenty 顶层 Agent 控制面

## 1. 设计结论

一个可长期运行的 Agent 不等于一次 Runtime 调用，也不等于一个 prompt 文件。Agenty 的 Agent Harness 负责身份、约束、上下文、记忆、技能、任务、审计和写回；`RuntimeMachine` 只是受控执行后端。

```text
Agent Harness
├── Identity / Policy / Memory / Skills / Users
├── Context Resolver
├── Task Registry / Scheduler
├── AgentyMachine（Goal / Environment / Action / Strategy / Reward）
├── RuntimeMachine（OpenCode / Codex / Claude Adapter）
├── Evidence / Event Ledger
└── Deliver / Approval / Rollback
```

## 2. Agent Workspace

每个可执行 Agent 都拥有一个完整、可审计的工作根，而不是只有名称和 prompt：

```text
agent-root/
├── AGENTS.md              # 行为约束与安全上限
├── Identity.md            # agent_id、名称、职责、组织血缘
├── MEMORY.json            # 稳定核心记忆
├── memory/                # 较大、按主题/日期保存的记忆
├── config/                # 非敏感配置
├── credential/            # 独立凭据边界，不自动继承
├── skills/SKILL_INDEX.md  # 能力索引
├── users/                 # 用户上下文
├── TASK.md                # 当前任务合同
├── project/               # 产品或目标项目
├── current/ todo/ backlog/
├── change/ locate/
└── runtime/               # Agent 运行状态与证据引用
```

运行时事件、模型输出和敏感数据不写入 Git；大体量运行证据放在外部数据区，工作区只保存引用和必要快照。

## 3. 递归上下文解析

```text
L0 根工作区 → L1 公共 agents 层 → L2 具体 Agent 层 → L3 项目/任务目录
```

父层先加载，子层后加载，并生成不含秘密正文的 `context_manifest`。Manifest 记录层级路径、资源哈希、选定技能、覆盖关系、有效身份和权限结果。

| 资源 | 合并规则 |
|---|---|
| `AGENTS.md` | 远到近累积，近层覆盖一般规则；安全上限不可取消 |
| `Identity.md` | 近层具体化身份，保留父级血缘 |
| `MEMORY.json` | 对象递归深合并；数组整体替换；`null` 清除继承 |
| `config/` | 近层覆盖，但不得扩大权限 |
| `credential/` | 不自动合并，任务显式选择引用 |
| Skills | 各层取并集，同名近层覆盖 |
| `users/` | 通用用户事实叠加 Agent 专属事实 |
| `current/todo/change` | 不合并，写入事实归属的最近层 |

有效权限始终是：

```text
环境硬上限 ∩ 上级授予范围 ∩ Agent 身份权限 ∩ 当前任务授权 ∩ 实际凭据能力
```

## 4. 任务与执行链路

`TASK.md` 是 Agent 可读的任务合同；机器调度以版本化 Task Registry 为准。

```text
任务触发
  → Registry 解析 executor_agent_id
  → Context Resolver 冻结上下文与 manifest
  → acquire 生成 EvidenceEnvelope
  → core 确定性规则形成 L0 Decision
  → 按风险唤起 Agent（L1/L2）或请求人（L3）
  → AgentyMachine 形成 Action/Strategy
  → RuntimeMachine 执行受控 Turn
  → deliver 通过授权门执行、回滚与验证
  → 写入唯一 outcome、证据和必要记忆
```

模型只能提出 `Decision` 或 `ActionIntent`，不能凭文本获得外部副作用权限。

## 5. 分级唤起

- **L0**：确定性检查新鲜度、完整性、阈值、历史和资源状态；稳定时直接结束。
- **L1**：小模型做分类、解释、观察建议和升级判断，不得批准动作。
- **L2**：大模型做高风险复核、候选方案、回滚和验证计划，仍只产生建议。
- **L3**：人类对未预授权、不可逆或高爆炸半径动作作明确授权。

同一 Agent 的不同模型档位共享身份、规则、记忆和任务合同；每次唤起使用独立 manifest 和 `run_id`。

## 6. 与双状态机的边界

`AgentyMachine` 管理 Agent 是谁、当前目标和策略以及结果写回；`RuntimeMachine` 管理 Runtime 版本、能力、Session、模型、交互、Turn 和结果。两者只通过公共命令、事件、Snapshot 和 Result 协作。

当前 `agenty run` 只覆盖 RuntimeMachine 的最小调用链，不是 Harness、AgentyMachine 或 Anna 的完成证明。

## 7. 实施顺序

1. Agent Workspace、Identity、权限和资源边界合同。
2. Context Resolver、深合并、Skill 覆盖和 `context_manifest`。
3. Task Registry、`TASK.md`、运行快照与分层写回。
4. AgentyMachine 的 Goal/Environment/Action/Reward 公共模型。
5. acquire/core/Agent/deliver、事件账本、审批和恢复。
6. 创建 `agents/anna/`，接入现有 RuntimeMachine，完成端到端验收。

以上是 M1 后续设计，不提前冻结具体版本号。
