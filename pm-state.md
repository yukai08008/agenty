# 项目状态: agenty

> 最近更新: 2026-09-05 | 更新者: Codex PM

## 里程碑

### M1 Anna (ACTIVE)

- 目标：完成第一个由应用触发、通过独立 Runtime 执行的层级化 Agent。

## 版本状态树

### v0.01 (ACTIVE) — Runtime 接入基线

- **v0.01-a Runtime 公共协议** (CODE_COMPLETE)
  - 分支：`v0.01-a`
  - 已定义 Availability、Channel、Session、Turn 四类独立状态
  - 已定义标准事件名称、RuntimeIdentity、RuntimeEvent 和聚合 RuntimeSnapshot
  - 质量门：15 项 pytest 通过、compileall 通过、diff check 通过、data 未被 Git 追踪
  - 工具缺口：项目未配置 ruff，未形成 lint 结论
- **v0.01-b Capability 与 AvailabilityMachine**（待创建）
  - **issue-capability-evidence-scope** (FOUND)：现有 probe 将帮助参数直接视为已验证能力，缺少版本、通道、证据等级和约束
- **v0.01-c OpenCode 1.18.26 Probe**（待创建）

## 历史分支

- `feature/file-agent-foundation` (ABANDONED)：方向确认前过早实现；保留本地提交作为历史，不合并、不推送。
- `feature/runtime-machine-opencode`：v0.01 拆分前的工作基线；后续从 `v0.01-a` 继续按 Feature 推进。

## 当前焦点

- 验收 v0.01-a 能力边界；确认后进入 v0.01-b。

## 待办

- [x] 确认 AgentyMachine 与 RuntimeMachine 独立协作
- [x] 建立 M1 > 版本 > 功能分支的层级
- [x] 落地双状态机和 Runtime Machine 设计文档
- [x] 定义 Runtime 状态、事件、能力和错误模型
- [x] 实现 OpenCode 无副作用探测
- [x] 回到 AgentyMachine 校准顶层所需事件
- [x] 基于 OpenCode 1.18.26 完成功能域抽象
- [x] 设计 Availability/Channel/Session/Turn 聚合状态机
- [x] v0.01-a：落地 Runtime 公共协议和合同测试
- [ ] 修正 capability 的版本、通道和证据模型
- [ ] 再推进 OpenCode 配置与会话切片

## 不变量

- 里程碑由若干版本完成，不能把里程碑等同于版本。
- 顶层与底层任务交替推进，在 Anna 完整链路处交汇。
- RuntimeMachine 与 AgentyMachine 不共享内部状态。
- OpenCode 是首个实现，不是公共协议本身。
