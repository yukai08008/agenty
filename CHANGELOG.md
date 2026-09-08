# Changelog

本文件记录 Agenty 已经发生的产品和架构变化。它不是原始 Git 日志：只记录影响公共行为、设计边界或验证证据的改动。

状态约定：

- `CODE_COMPLETE`：代码和默认自动测试完成，但不代表正式发布。
- `live verified`：在明确 Runtime 版本上调用过真实模型或真实通道。
- `probe verified`：只完成无副作用探测，不代表实际执行能力。
- 当前版本位置见 `pm-state.md`，未来目标见 `ROADMAP.md`。

## Unreleased - v0.06 Minimal Runtime-backed CLI

### v0.06-a - `agenty run`（CODE_COMPLETE, live verified，2026-09-08）

Added:

- `run_opencode_task()` 应用入口：通过 RuntimeAdapterRegistry、RuntimeSelectionMachine 和 RuntimeTurnRunner 选择精确 OpenCode 1.18.26 并执行一次 Turn。
- `agenty run TASK...`，支持 `-C/--directory`、`--auto-approve`、`--timeout`、`--opencode` 和 `--json`。
- CLI 退出码合同：成功为 0、Turn 非成功终态为 1、Turn 前设置失败为 2、用户中断为 130。

Changed:

- 早期 `greet/think/status` 固定 demo 被真实自然语言 Runtime 任务替代。
- deny 模式禁用项目配置、外部技能和默认插件，通过专用 Agent 的 `permission: deny` 与 `--pure` 执行，并在 Turn 前解析和复验最终配置，确保所有 MCP disabled 且权限未被 ambient/managed 配置覆盖；验证失败时拒绝启动 Turn。
- OpenCode 子进程使用独立进程组，并在 CLI 中断、timeout 或 cancel 时回收，避免后台遗留执行。
- 人类输出展示 Runtime、Session、usage、文件变化和证据日志；JSON 模式输出完整不可变 TurnResult。

Validation:

- 累计默认回归：204 passed、1 个显式 live 测试默认 skipped。
- deny 模式 live 验证中，OpenCode 1.18.26 明确报告无 Shell 工具可用，仍返回可审计成功 Turn、Session、usage、零文件变化和日志。
- 显式 `--auto-approve` live 验证成功执行只读 `df`：Session `ses_f7f113ccaffeDMDRNqeqVKpgog`、23292 tokens、0 USD、0 个文件变化，并生成 normalized/raw 日志。
- 较宽的只读代码审查任务在显式 180 秒限制下到达 `turn_timeout`，CLI 正确返回非成功终态、退出码 1、零文件变化和事件证据；它不计作成功验收。

Limitations:

- CLI 尚不支持 AgentyMachine、Anna、分层配置/记忆/技能、模型/effort 选择或 Session resume。
- OpenCode transient_process 没有中途审批往返；需要工具时用户必须理解并显式选择 `--auto-approve`。
- 结果和事件日志仍是单次执行的本地证据，没有长期 retention 或 cleanup policy。

## Unreleased — v0.05 RuntimeMachine 六类应用职责

### v0.05-f — 监控与结果（CODE_COMPLETE, live verified，2026-09-07）

Added:

- Runtime 中立的 `RuntimeUsage`、`RuntimeArtifact`、`ArtifactManifest`、`EventLogRef` 和不可变 `TurnResult`。
- 限流、额度耗尽、认证失败、模型不可用和 Runtime crash 公共失败代码，以及保留明确 retryable 证据的分类器。
- OpenCode 1.18.26 `step_finish` token/cost 归一化和安全的 `FreeUsageLimitError`、认证及模型错误 reason 提取。
- 每次执行独立的 normalized/raw JSONL 证据目录、摘要、事件数量和严格 JSON 边界。

Changed:

- `RuntimeTurnRunner.run()` 返回终态 `TurnResult`，并保证 snapshot、Adapter、结果输出或异常处理失败后释放活动 Turn。
- Adapter 直接发出的失败终态与异常失败使用同一分类路径；终态后的额外事件转换为 `invalid_output`。
- RuntimeTurnRequest 和 ProjectEnvironment 将工作目录规范化为绝对路径，避免持久化结果随恢复进程 cwd 漂移。
- 文件产物只表达 Turn 前后观察到的普通文件内容差异，producer 固定为 `unknown:filesystem_observation`，不把并发文件变化错误归因给 Runtime。

Validation:

- 累计默认回归：183 passed、1 个 live 测试 skipped。
- RS-01 至 RS-08 已自动化；覆盖 429/FreeUsageLimit、quota/auth/model/crash/timeout、usage 聚合、证据隔离、日志路径碰撞、提交期取消、异常清理和 TurnResult JSON 恢复一致性。
- `compileall`、涉及文件 Ruff、`git diff --check` 和 `git ls-files data/` 门禁通过。
- OpenCode 1.18.26 transient_process 已通过一次真实磁盘使用检查：Turn 成功、Session/usage/normalized 与 raw 日志均可追踪，ArtifactManifest 完整且无文件变化；失败分支仍由公共合同测试与假进程 integration 覆盖。

Limitations:

- JSONL 是终态后的证据导出，不是进程崩溃时逐事件落盘的耐久 journal。
- ArtifactManifest 不表示删除、symlink 或仅元数据变化；文件扫描可能受执行外并发写入影响，并通过 `scan_complete` 与 `limitations` 暴露边界。
- 原始事件日志可能含敏感诊断数据；当前使用私有目录和文件权限，但尚无长期保留、清理或脱敏策略。

### v0.05-e — 交互管理（CODE_COMPLETE，2026-09-06）

Added:

- Runtime 中立的 InteractionPolicy、ApprovalRequest、ApprovalDecision 和授权审计事件。
- RuntimeInteractionMachine，支持默认拒绝、ask 暂停/恢复、显式 auto、request ID 校验、审批超时和 actor 审计。
- Runner cancel 控制与 OpenCode 子进程回收。

Changed:

- RuntimeTurnRequest 默认使用 `deny_by_default`，不会隐式开启 auto。
- OpenCode 1.18.26 只有显式 `auto_approve` 才映射 `--auto`。
- `transient_process + JSON` 明确不支持审批往返，ask 在进程启动前被 capability guard 拒绝。

Validation:

- 累计默认回归：142 passed、1 个 live 测试 skipped。
- IN-01 至 IN-07 已自动化，覆盖自动/人工决策审计、错误 request ID、审批回复失败、取消回收和超时终态。
- 本阶段未调用真实模型；auto/cancel 为 integration verified，ask 不支持结论绑定 OpenCode 1.18.26 transient_process Channel。

### Documentation structure（2026-09-06）

- 新增 `ROADMAP.md` 作为产品目标、M1 完成定义与阶段顺序的唯一真相源。
- 新增 `CHANGELOG.md`，从实际 Git 血缘重建版本级行为变化、验证证据与限制。
- `pm-state.md` 收缩为当前状态；`AGENTS.md` 收缩为接手规范和文档路由。
- `MILESTONES.md` 保留为兼容入口，不再形成第二份路线图。

### v0.05-d — 模型与 effort（CODE_COMPLETE，2026-09-06）

提交：`732df2f`；交接文档：`81fcccb`

Added:

- Runtime 中立的 ModelRef、ModelSelection、ModelDescriptor、ModelCatalog 和 ModelBinding。
- RuntimeModelSelectionMachine，分离 desired 与 effective。
- OpenCode 1.18.26 `models --verbose` 目录解析和版本绑定证据。

Changed:

- RuntimeTurnRequest 不再接受未经校验的 model/effort 字符串，只接受 RuntimeModelBinding。
- OpenCode Adapter 通过 binding 映射 `--model provider/model` 与可选 `--variant effort`。

Validation:

- 累计默认回归：125 passed、1 个 live 测试 skipped。
- 本机无模型调用探测得到 160 个动态目录项；默认 live 模型仍存在。
- effective 只有 integration/live 执行证据才能写入，目录探测不能冒充实际生效证据。

Limitations:

- 本阶段未重新调用真实模型，也未验证具体 effort 的真实行为。
- 模型目录是动态外部状态，数量不能硬编码。

### v0.05-c — 会话管理（CODE_COMPLETE，2026-09-06）

提交：`82bfa08`

Added:

- ProjectEnvironment、RuntimeSessionRequest、RuntimeSessionBinding。
- SessionMachine、可持久化 binding catalog 和 new/resume coordinator。
- READY/BUSY、关闭、丢失和失败重试状态路径。

Changed:

- OpenCode 1.18.26 只有在 Runtime Session 与 Project Environment binding 校验通过后才使用 `--session`。
- Adapter 校验返回事件中的 Session ID，阻止会话上下文漂移。

Validation:

- 累计默认回归：105 passed、1 skipped。
- 未知 Session、Environment 不匹配、重复 binding 和 Runtime 错配均在执行前阻断。

Limitations:

- 只实现 new/resume；原生 fork 尚未纳入 Agenty 执行分支语义。
- binding catalog 当前是可持久化模型加内存边界，长期存储尚未实现。

### v0.05-b — 事件归一化（CODE_COMPLETE，2026-09-06）

提交：`3b1b24b`

Added:

- OpenCodeEventNormalizer，固定解释 OpenCode 1.18.26 JSONL。
- RuntimeEventStreamMachine，分配连续 sequence 并锁定 Runtime、correlation、Turn 和 Session 上下文。
- 独立 RuntimeRawEventRecord 诊断记录。

Changed:

- RuntimeTurnRunner 只把去除 raw JSON 的公共事件交给状态机。
- 未知/畸形事件和上下文漂移转换为结构化 invalid_output。

Validation:

- 累计默认回归：90 passed、1 skipped。

### v0.05-a — Runtime 类型与版本选择（CODE_COMPLETE，2026-09-06）

提交：`4a436c9`

Added:

- RuntimeTarget，要求应用给出 Runtime 类型和精确版本。
- RuntimeAdapterRegistry 与 RuntimeSelectionMachine。
- 未注册版本、探测身份不一致和 Adapter 工厂异常的结构化拒绝。

Validation:

- 累计默认回归：69 passed、1 skipped。
- 本机 OpenCode 1.18.26 通过新选择机进入 SELECTED。

## v0.03 — Runtime 最小 Turn 调用链（CODE_COMPLETE）

### v0.03-c — 显式真实模型冒烟（2026-09-06）

提交：`a035a0e`

Added:

- 由 `AGENTY_LIVE_OPENCODE=1` 显式开启的真实模型测试；默认测试不访问模型。

Validation:

- OpenCode 1.18.26 + `opencode/nemotron-3.5-lightning-free` 成功完成真实新 Session Turn。
- `opencode/mimo-v2.5-free` 返回 HTTP 429，调用链保留 Session 和安全的结构化错误详情。

Limitations:

- 只验证新 Session、显式 model、JSON、文本输出和终态；不覆盖 effort、resume、fork 或审批。

### v0.03-b — OpenCode JSON Turn Adapter（2026-09-06）

提交：`5eb6f72`

Added:

- OpenCode 1.18.26 同步 JSONL Turn Adapter 和通用 RuntimeTurnRunner。
- 成功、Runtime error、tool error、非零退出、畸形 JSON、超时和目录缺失回归。

Changed:

- 同时以进程 cwd 和 `--dir` 绑定工作目录。
- prompt 放在 `--` 后，默认不传 auto、resume 或 fork。

### v0.03-a — 公共 Turn 合同（2026-09-06）

提交：`3e230a2`

Added:

- Pydantic RuntimeTurnRequest、TurnStateData 和普通 Python TurnMachine。
- Runtime、Turn、Session、correlation 上下文守卫及 JSON 往返恢复。

## v0.01 — Runtime 接入基线（CODE_COMPLETE）

### v0.01-c — OpenCode Probe 迁移（2026-09-05）

提交：`80be93f`

Changed:

- OpenCode 1.18.26 Probe 迁入公共 Runtime 协议。
- help 中的选项只形成 `support=unknown / evidence=advertised`，不再被误报为已验证能力。

### v0.01-b — Capability 与 AvailabilityMachine（2026-09-05）

提交：`a002ba2`、`a9605c2`

Added:

- 与 Runtime 版本、Channel、支持状态、证据和约束绑定的 CapabilityRecord。
- AvailabilityMachine 和结构化探测失败。

Corrected:

- 早期 dataclass 状态不符合项目约束，随后统一迁移为 Pydantic v2 并增加恢复测试。

### v0.01-a — Runtime 公共协议（2026-09-05）

提交：`d30b496`、`7b2fc99`

Added:

- Availability、Channel、Session、Turn 四类独立状态与标准事件。
- RuntimeIdentity、RuntimeEvent、RuntimeSnapshot。
- Session lineage 必须与项目 Environment 共同锁定的设计约束。

## Earlier history

### 双状态机设计与 OpenCode 研究（2026-09-05）

提交：`9c4a055`、`06315ae`、`0a120be`、`8784a82`

- 确定 AgentyMachine 与 RuntimeMachine 独立协作。
- 以本机 OpenCode 1.18.26 为首个 Runtime 样本，建立状态、事件和能力基线。

### File-agent foundation 尝试（ABANDONED）

分支：`feature/file-agent-foundation`；提交：`cc4425a`、`49c49fb`、`7e368d2`

- 曾尝试直接实现文件化 Agent 加载和 Codex Runtime。
- 因在总体层级、双状态机和版本边界确认前过早实现而放弃；分支保留为历史，不合并。

### 初始 CLI

提交范围：`5f798f3` 至 `9876fda`

- 建立 uv Python CLI、安装/升级、Rich/Questionary 交互和 API key 配置。
- 这些能力是当前仓库的早期外壳，不代表最终 Agent 架构。
