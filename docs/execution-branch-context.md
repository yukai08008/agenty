# 执行分支上下文需求

> 状态：需求已确认，实现方案未定
>
> 范围：M1 Anna 的后续设计约束；不纳入 v0.01-a。

## 1. 核心需求

Runtime 原生的 Session fork 只处理会话上下文，不足以代表 Agenty 中完整、可恢复的执行分支。

Agenty 的一次执行分支至少需要同时锁定：

```text
ExecutionBranch = RuntimeSessionLineage + ProjectEnvironment
```

- `RuntimeSessionLineage`：Runtime、版本、父子 Session 关系和当前 Session。
- `ProjectEnvironment`：该 Session 观察并操作的项目环境。

只恢复 Session 而没有恢复或验证对应项目环境，不得视为恢复了同一个执行分支。

## 2. 必须显式记录的三个方面

### Env

记录 Action 发生时面对的项目和运行环境。候选内容包括工作目录、仓库、revision、branch/worktree、未提交状态、Runtime Profile、工具和权限。具体字段及快照机制尚未决定。

### Action（Strategy）

记录 Agent 做了什么，以及采用了什么策略。Action 不能只剩一段自然语言结果；需要保留目标、策略标识或描述、输入和实际执行之间的关联。Strategy 的表达形式尚未决定。

### Reward

记录 Action 在相应 Env 中产生的评价结果和证据。Reward 暂不限定为单个数值，可以是多维、延迟产生或由不同评价者给出的结果。计算、归因和聚合方式尚未决定。

## 3. 约束

- 原生 Session fork 只能作为 Runtime 层能力，不能单独创建 Agenty 执行分支。
- 恢复或分叉时必须同时校验 Session lineage 与 Env identity。
- `Env → Action(strategy) → Env' → Reward` 的关系需要可追踪。
- Session 与 Env 不匹配时不能静默继续，后续协议必须选择重建环境、创建新分支或阻断执行。
- Session fork 不提供文件系统隔离；需要时由 Agenty 另行管理 worktree、容器或其他环境快照。

## 4. 尚未决定

- 是否使用 OpenCode 原生 Session fork，或由 Agenty 自己重放上下文。
- Env 的最小标识、完整快照边界和隔离手段。
- Strategy 属于 Action 字段、独立对象还是策略状态机。
- Reward 的来源、尺度、评价时间和写入记忆的规则。
- ExecutionBranch 由 AgentyMachine 管理，还是形成独立子状态机。

