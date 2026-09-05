# 项目状态: agenty

> 最近更新: 2026-09-05 | 更新者: Codex PM

## 里程碑

### M1 Anna (ACTIVE)

- 目标：完成第一个由应用触发、通过独立 Runtime 执行的层级化 Agent。

## 版本状态树

### v0.01 (ACTIVE) — Runtime Machine 与 OpenCode 底层适配

- **feature/runtime-machine-opencode** (DEVELOPING)
  - 底层切片 1：Runtime 状态模型、公共协议和 OpenCode `probe`（完成，10 项测试通过）
  - 顶层切片 1：AgentyMachine `RESOLVING_RUNTIME` 协议校准（完成设计）
  - 当前切片：等待确认后进入 Runtime 配置（model/effort）

## 历史分支

- `feature/file-agent-foundation` (ABANDONED)：方向确认前过早实现；保留本地提交作为历史，不合并、不推送。

## 当前焦点

- 确认第一次交汇结果，再推进 RuntimeMachine 配置切片。

## 待办

- [x] 确认 AgentyMachine 与 RuntimeMachine 独立协作
- [x] 建立 M1 > 版本 > 功能分支的层级
- [x] 落地双状态机和 Runtime Machine 设计文档
- [x] 定义 Runtime 状态、事件、能力和错误模型
- [x] 实现 OpenCode 无副作用探测
- [x] 回到 AgentyMachine 校准顶层所需事件
- [ ] 再推进 OpenCode 配置与会话切片

## 不变量

- 里程碑由若干版本完成，不能把里程碑等同于版本。
- 顶层与底层任务交替推进，在 Anna 完整链路处交汇。
- RuntimeMachine 与 AgentyMachine 不共享内部状态。
- OpenCode 是首个实现，不是公共协议本身。
