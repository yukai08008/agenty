# 项目状态：Agenty

> 最近更新：2026-09-07
>
> 当前状态只记录“现在在哪里”；目标见 `ROADMAP.md`，历史见 `CHANGELOG.md`。

## 文档入口

- 接手规范：`AGENTS.md`
- 总体目标与阶段：`ROADMAP.md`
- 历史变更与证据：`CHANGELOG.md`
- 当前版本三件套：`dev_plans/v0.03-v0.05/`
- 架构知识入口：`vault/00-index/home.md`

## 里程碑状态

### M1 Anna（ACTIVE）

目标：完成第一个由应用触发、按根级与 Agent 局部层级加载、通过独立 RuntimeMachine 执行并可审计收尾的 Agent Anna。

当前判断：RuntimeMachine 六类应用职责底座已完成；AgentyMachine、层级加载、记忆/技能和 Anna 本体尚未实现。M1 仍需多个版本。

## 版本状态树

### v0.05 RuntimeMachine 应用侧完整职责（CODE_COMPLETE）

父基线：`v0.03-c@a035a0e`

- `v0.05-a` Runtime 类型与精确版本选择（CODE_COMPLETE）— `4a436c9`
- `v0.05-b` 事件归一化（CODE_COMPLETE）— `3b1b24b`
- `v0.05-c` Session 与 Environment binding（CODE_COMPLETE）— `82bfa08`
- `v0.05-d` 模型与 effort（CODE_COMPLETE）— `732df2f`
- `v0.05-e` 交互管理（CODE_COMPLETE）— `f5f37ea`
- `v0.05-f` 监控与结果（CODE_COMPLETE, live verified，当前未提交）

已完成版本：v0.01 Runtime 接入基线、v0.03 最小 Turn 调用链。细节见 `CHANGELOG.md`。

## 当前 Git 与验证

- 当前分支：`v0.05-f`
- 当前 HEAD：`f5f37ea`；v0.05-f 为未提交实现
- 最新 HEAD 必须从 Git 读取，不在状态文件中复制易过期的提交号
- 自动回归：183 passed、1 个显式 live 测试默认 skipped
- OpenCode：1.18.26，首个适配通道为 `transient_process`
- v0.05-f 已通过 OpenCode 1.18.26 transient_process 真实磁盘使用检查；成功路径包含 Session、usage、事件日志和零文件变化证据，失败路径来自公共合同测试与假进程 integration

## 当前工作区注意事项

- `pyproject.toml` 和 `uv.lock` 有用户为 IPython 增加依赖产生的未提交修改。
- 后续 Agent 必须先重新检查这些修改，不能擅自回退或夹带进功能提交。
- 全项目仍有早期 lint 基线；v0.05-f 涉及文件在排除既有 `UP037` 与 Runner 广义异常边界后 Ruff 已通过。

## 当前焦点

1. 提交并推送用户已验收的 v0.05-f，排除用户自己的 IPython 依赖修改。
2. 按用户确认建立 v0.06-a，提供基于现有 RuntimeMachine 的最小 `agenty run` CLI。
3. 使用新 CLI 完成一次真实 OpenCode 体验验证，但不将其描述为完整 AgentyMachine 或 Anna。

## 后续硬约束

- Runtime 类型、精确版本、Channel 和能力证据共同确定 Adapter 行为。
- Session resume 同时校验 Runtime Session lineage 与 ProjectEnvironment。
- 模型/effort 在 Turn 前校验，desired/effective 分离。
- auto 默认关闭，所有授权决策可审计。
- 顶层与底层交替设计，在 Anna 完整链路处交汇。
- 默认测试不调用真实模型，运行时数据不进入 Git。
