# 项目状态: Agenty

> 最近更新: 2026-09-01 | 更新者: Codex PM

## 状态树

### v1.01 (ACTIVE) — 当前 API 版本

- **v1.01-a control-plane-state** (MERGED)：多 Agent 注册、runtime 配置、状态快照、事件与 checkpoint
- **v1.01-b workspace-suite** (MERGED)：Worker 工作空间、agent suite 与基础项目快照场景
- **v1.01-c cli-migration** (MERGED)：第一批 CLI、安全迁移、Git 初始化与端到端验收

### legacy 0.1.0 (ARCHIVED)

- 原始 Demo CLI，仅作为迁移基线，不满足 v1.00 封板标准，不补打 `v1.00-final`

## 当前焦点

- v1.01 POC 已通过验收，等待使用反馈；下一步将结果收敛为 v1.02 正式版计划

## 待办

- [x] 完成 v1.01-a 并通过状态机测试
- [x] 推进 v1.01-b 的 suite 基础场景
- [x] 推进 v1.01-c 的 CLI 与迁移闭环
- [x] 写入 `TEST_CASES_FINAL.md`
- [ ] 将 v1.01 结果作为 v1.02 Web/正式发布版的 API 基线

## 版本说明

- v1.01 是奇数 API 版，完成后不打正式发布 tag。
- Python 包版本暂保留 `0.1.0`；正式版本映射在 v1.02 前单独决策，避免 `v1.01` 被 PEP 440 归一化产生歧义。
- 本版本从 `main@9876fda` 的 legacy Demo 启动，属于首次纳入 PM 状态机的 bootstrap 例外。
