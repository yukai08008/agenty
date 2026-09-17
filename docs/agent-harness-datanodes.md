# Agent Harness DataNode 设计

> 状态：`PROPOSED`
> 范围：Agenty Harness 的运行时领域节点
> 原则：先确定节点，再设计 FSM、存储和调度

## 1. 分类结论

Harness 只保留真正有稳定身份、独立语义和可验收不变量的节点。节点分为两类：

- **业务类节点**回答“Agent 为用户形成了什么事实”。它们不随一次进程重试而改变身份。
- **运行类节点**回答“这项工作如何被可靠执行、依据什么证据收尾”。它们服务于业务结果，但不冒充业务结果。

交互式节点关系图见 [`agent-harness-datanodes.html`](agent-harness-datanodes.html)。HTML 图支持点击每个节点查看稳定身份、事实字段、不变量和当前实现状态；本 Markdown 继续作为完整模型规范源。

## 2. 已确定的核心节点

### 2.1 `AgentIdentity` — 业务/控制类

代表一个长期存在、可被用户委派的 Agent 身份，不代表某次进程。

- **稳定身份**：`agent_id`，在一个 Agent Workspace 内唯一。
- **事实字段**：`name`、`role`、父级身份引用。
- **持有者**：Agent Workspace 的 Identity 层。
- **创建/失效**：建立或废弃 Agent 时变化，不随任务运行失效。
- **不变量**：`agent_id` 非空且不可在一次执行中改变；子 Agent 必须保留父级血缘。
- **当前映射**：`src/agenty/harness.py:AgentIdentity`；Anna 的 `agents/anna/Identity.md`。

### 2.2 `AgentGoal` — 业务类

代表用户或上级 Agent 委派给身份的目标，是真正需要完成的业务意图。

- **稳定身份**：`goal_id`，在 Agent 身份范围内唯一。
- **事实字段**：目标描述、所属 `agent_id`、可验收条件引用。
- **持有者**：AgentyMachine；由用户任务或上级 Agent 创建。
- **生命周期**：提出、执行中、完成或放弃；具体状态交给 FSM 设计。
- **不变量**：目标必须绑定一个 `AgentIdentity`，不能用 `task_id` 代替目标身份。
- **当前映射**：`src/agenty/machine.py:Goal`；当前 `application.py` 暂以 `task_id` 填充描述，属于临时占位，不能视为最终业务模型。

### 2.3 `AgentOutcome` — 业务类

代表向用户交付的结果摘要、产物和可追溯证据；它不是 Runtime Turn 的镜像。

- **稳定身份**：`outcome_id`。
- **事实字段**：`goal_id`、结果摘要、产物引用、证据引用、是否满足验收。
- **持有者**：AgentyMachine/应用收尾层；Runtime 只能提供证据。
- **生命周期**：候选、已验收、被拒绝或 superseded。
- **不变量**：必须引用一个 `goal_id` 和至少一个执行事实；不能仅因进程成功就标记业务成功。
- **当前映射**：尚无独立节点；`AgentRunResult` 和 `TurnResult` 是外部组合/运行结果，不能直接作为最终业务节点。

### 2.4 `MemoryFact` — 业务类

代表可长期复用的、归属于某一层 Agent 的记忆事实。一次执行产生的文本不是记忆事实本身。

- **稳定身份**：`fact_id`，在归属层唯一。
- **事实字段**：内容、来源 `outcome_id`、置信度/状态、归属层。
- **持有者**：对应 Workspace 层；父层与子层不能共同无主写入。
- **生命周期**：候选、确认、修订、失效。
- **不变量**：写回必须有来源结果和明确目标层；冲突不能静默覆盖。
- **当前映射**：`memory.py` 目前直接修改 `MEMORY.json` 并记录 `MemoryWriteAudit`；该操作应视为 Fact 写回适配器，尚未形成独立 `MemoryFact` 节点。

## 3. 已确定的运行类节点

### 3.1 `TaskDefinition` — 运行类

代表机器可调度的任务合同，不等于用户目标，也不等于 `TASK.md` 文件。

- **稳定身份**：`task_id`，Registry 内唯一。
- **事实字段**：执行 Agent、Agent 根、Task 合同引用、Runtime 策略、权限上限、启用状态。
- **持有者**：Task Registry。
- **生命周期**：注册、启用/停用、废弃；单次执行不改变定义身份。
- **不变量**：执行 Agent 根和合同必须在 Workspace 内；`TASK.md` 不能成为机器调度的第二真相源。
- **当前映射**：`src/agenty/task_registry.py:TaskSpec`；`agents/task_registry.json`。

### 3.2 `ContextManifest` — 运行类

代表一次执行实际加载到的身份、规则、记忆、配置和 Skill 集合，是可重放边界，不是配置仓库。

- **稳定身份**：`manifest_id`/`run_id`。
- **事实字段**：层级顺序、资源路径与 SHA-256、覆盖关系、有效身份、有效权限、manifest digest。
- **持有者**：Context Resolver；执行开始后不可变。
- **生命周期**：生成、引用、过期；不能被后续层静默改写。
- **不变量**：不含秘密正文；资源顺序稳定；必须能重建当时的有效上下文。
- **当前映射**：`src/agenty/harness.py:ContextManifest`，已具备资源排序和 digest。

### 3.3 `AgentExecution` — 运行类

代表一次由 AgentyMachine 管理的执行实例，连接一个任务、目标、环境和最终业务结果。

- **稳定身份**：`execution_id`，每次尝试唯一，重试不能复用。
- **事实字段**：`task_id`、`agent_id`、`goal_id`、环境引用、manifest 引用、执行结果引用、失败原因。
- **持有者**：AgentyMachine。
- **生命周期**：创建、上下文解析、计划、执行、收尾、阻断/等待人工；状态交给 FSM。
- **不变量**：只能引用一个冻结 Manifest；不能把 Runtime Session ID 当成执行身份；同一 execution 不得产生两个权威 outcome。
- **当前映射**：`src/agenty/machine.py:AgentSnapshot` 和 `application.py` 中的机器实例；目前尚未有独立 `execution_id` 字段，是下一实现缺口。

### 3.4 `RuntimeTurn` — 运行类

代表 RuntimeMachine 实际执行的一次 Turn，负责 Runtime 版本、Session、事件、usage、artifacts 和失败事实。

- **稳定身份**：`turn_id`；Session lineage 和 ProjectEnvironment 共同约束接续。
- **事实字段**：Runtime identity、request、终态、事件日志、usage、artifact、failure。
- **持有者**：RuntimeMachine；AgentyMachine 只能通过公共 Result 引用。
- **生命周期**：由现有 TurnMachine/Runner 管理。
- **不变量**：Runtime 厂商字段不泄漏到公共业务节点；Turn 成功不自动等于 Goal 成功。
- **当前映射**：`RuntimeTurnRequest`、`TurnResult`、`TurnMachine`、`RuntimeTurnRunner`。

### 3.5 `AuthorizationDecision` — 运行类

代表一次针对工具或副作用的授权事实，而不是布尔 `auto_approve` 参数。

- **稳定身份**：`decision_id`。
- **事实字段**：execution/turn 引用、请求动作、策略、决定者、时间、结果和审计引用。
- **持有者**：Interaction/Approval 层；人类或策略系统作出决定。
- **生命周期**：请求、批准/拒绝、过期；具体迁移交给 FSM。
- **不变量**：默认拒绝；未授权动作不能执行；模型输出不能直接充当授权。
- **当前映射**：`RuntimeInteractionPolicy`、`RuntimeApprovalDecision` 和 `RuntimeInteractionMachine`；尚未抽出独立跨 Harness 节点。

## 4. 集中式 Pydantic 数据模型草案

下面是节点的集中式模型草案。它们表达运行时领域语义，不等同于 JSON 文件、数据库表或 CLI DTO。第一版统一使用 Pydantic v2、`extra="forbid"`；真正进入代码前，先由用户确认开放取舍。

```python
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AgentIdentity(Node):
    agent_id: str
    name: str
    role: str | None = None
    parent_agent_id: str | None = None


class AgentGoal(Node):
    goal_id: str
    agent_id: str
    description: str
    acceptance_refs: tuple[str, ...] = ()


class AgentOutcome(Node):
    outcome_id: str
    goal_id: str
    execution_id: str
    summary: str
    artifact_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    acceptance: Literal["candidate", "accepted", "rejected", "superseded"] = "candidate"

    @model_validator(mode="after")
    def requires_execution_evidence(self) -> "AgentOutcome":
        if not self.execution_id or not self.evidence_refs:
            raise ValueError("outcome requires execution_id and evidence_refs")
        return self


class MemoryFact(Node):
    fact_id: str
    owner_layer: str
    content: str
    source_outcome_id: str
    status: Literal["candidate", "confirmed", "revised", "invalid"] = "candidate"
    confidence: float | None = Field(default=None, ge=0, le=1)
    valid_until: datetime | None = None


class TaskDefinition(Node):
    task_id: str
    executor_agent_id: str
    agent_root: str
    task_contract_ref: str
    runtime_policy: dict[str, Any] = Field(default_factory=dict)
    permission_ceiling: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = False


class ManifestResource(Node):
    path: str
    kind: str
    sha256: str


class ContextManifest(Node):
    manifest_id: str
    run_id: str
    executor_agent_id: str
    loaded_layers: tuple[str, ...]
    resources: tuple[ManifestResource, ...]
    selected_skills: tuple[str, ...] = ()
    overrides: tuple[dict[str, str], ...] = ()
    effective_permissions: dict[str, Any] = Field(default_factory=dict)
    manifest_sha256: str


class AgentExecution(Node):
    execution_id: str
    task_id: str
    agent_id: str
    goal_id: str
    environment_id: str
    manifest_id: str
    turn_ids: tuple[str, ...] = ()
    outcome_id: str | None = None
    failure_code: str | None = None


class RuntimeTurn(Node):
    turn_id: str
    execution_id: str
    runtime_kind: str
    runtime_version: str
    session_id: str | None = None
    terminal_state: str
    event_log_ref: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: tuple[str, ...] = ()
    failure_code: str | None = None


class AuthorizationDecision(Node):
    decision_id: str
    execution_id: str
    turn_id: str | None = None
    action: str
    policy: Literal["ask", "auto", "deny", "cancel"]
    decided_by: Literal["policy", "agent", "user", "system"]
    approved: bool
    decided_at: datetime
    audit_ref: str | None = None
```

### 模型之间的最小引用约束

```text
AgentIdentity.agent_id
  → AgentGoal.agent_id
  → TaskDefinition.executor_agent_id
  → AgentExecution.agent_id

TaskDefinition.task_id + AgentGoal.goal_id
  → AgentExecution

AgentExecution.manifest_id
  → ContextManifest.manifest_id

AgentExecution.turn_ids
  → RuntimeTurn.turn_id

RuntimeTurn / AgentExecution
  → AgentOutcome.execution_id
  → MemoryFact.source_outcome_id
```

这些引用是跨节点的不变量，不代表对象必须嵌套保存。节点应保持单一事实源，外部 JSON/数据库只负责表示和索引。

## 5. 不作为核心 DataNode 的对象

- `AgentRunResult`：跨节点的应用 DTO，包含上下文、快照和 Runtime 结果，不是单一事实源。
- `ResolvedContext`：执行前的组合视图；其不可变审计部分由 `ContextManifest` 表达。
- `MemoryWriteAudit`：写回审计记录，引用 `MemoryFact`，不代替记忆事实。
- Runtime raw event、进程、线程、连接、锁句柄、缓存：诊断或资源，不是可持久化领域节点。
- `TASK.md`、`MEMORY.json`、JSON Registry：外部表示；节点模型优先于文件格式。

## 6. 需要保持开放的取舍

以下问题在实现前需要用户确认，不在本轮擅自冻结：

1. `AgentOutcome` 是否需要独立的用户验收动作，还是第一版只由应用收尾确认。
2. `MemoryFact` 的最小字段是否包含置信度、有效期和用户确认状态。
3. 一个 `AgentExecution` 是否允许包含多个 Runtime Turn；当前设计允许 1:N，但首版可限制为 1:N 的顺序 Turn。
4. `AuthorizationDecision` 是否进入统一事件账本，还是先沿用 RuntimeInteraction 的审计边界。
5. `TaskDefinition` 是否继续使用 JSON Registry，还是转为版本化 Pydantic Registry 文件。

## 7. 节点驱动的首批验收场景

- 相同 `task_id` 的重复触发产生不同 `execution_id`，不重复写入同一个 outcome。
- 子 Agent 不能修改父层 `AgentIdentity` 或扩大 `AuthorizationDecision` 的权限。
- Context Manifest 生成后修改源文件，不改变已冻结执行上下文；新执行生成新 digest。
- Runtime Turn 成功但业务验收失败时，`RuntimeTurn` 为成功而 `AgentOutcome` 不得伪装为成功。
- 记忆写回必须明确目标层、来源 outcome 和冲突字段；越权目标被阻断。

## 8. 下一步边界

节点确定后，再用 FSM 技能定义 `AgentExecution`、`AuthorizationDecision` 和 `MemoryFact` 的状态、事件、恢复和持久化；不要在节点尚未确认前扩展调度器、自动记忆或多 Agent 协作。
