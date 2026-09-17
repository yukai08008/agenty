# Agenty TODO

## Active

- [ ] **H1 Agent Harness 最小闭环** — 实现 Agent Workspace、递归 Context Resolver 与 Context Manifest。
  - [x] 定义 `AgentIdentity`、`ResolvedContext`、`ContextManifest` 公共模型
  - [x] 实现根 → 公共 agents → Agent → 项目/任务的层级解析
  - [x] 实现 Memory/config/Skills 的合并与 credential 引用边界（第一版）
  - [x] 实现路径逃逸与缺失核心文件阻断
  - [x] 增加离线回归测试（3 cases）
  - [x] 完善权限收紧/扩大校验与稳定 manifest 规范
  - [x] 建立 Demo Agent workspace fixture

## Next

- [ ] 确认并固化 Harness DataNode 最小字段与事实源
  - [x] 区分业务类与运行类节点
  - [x] 绘制节点关系与当前代码映射
  - [ ] 用户确认 AgentOutcome / MemoryFact / AgentExecution 取舍
- [ ] DataNode 确认后再用 FSM 技能定义生命周期、恢复与持久化
- [ ] Task Registry 与 `TASK.md` 任务合同
  - [x] JSON Registry 模型、唯一 task_id 校验与路径边界
  - [x] Agent 根和 `TASK.md` 合同存在性校验
  - [x] Registry → Resolver → AgentyMachine 编排入口（Runtime executor 注入）
  - [x] 注册任务接入 `run_opencode_task`
- [ ] 结果/记忆写回边界
  - [x] 结构化 outcome 写入显式 runtime-data 目录
  - [x] 记忆按层级归属写回与冲突审计
- [ ] AgentyMachine Goal/Environment/Action/Reward 最小状态机
  - [x] 生命周期状态、事件和公共模型
  - [x] 基本上下文/计划/执行/收尾转换
- [x] 接入现有 `run_opencode_task`（精确 Runtime 选择与 TurnResult）
- [ ] Anna Agent 定义与 RuntimeMachine 编排
  - [x] 建立最小 `agents/anna/` workspace（Identity/AGENTS/MEMORY/TASK）
  - [x] 注册 Anna 默认任务并完成端到端离线验收
