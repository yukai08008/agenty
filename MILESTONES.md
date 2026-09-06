# Agenty 里程碑

里程碑高于版本。一个里程碑由若干个可独立验收的版本逐步完成；版本下面再拆功能分支，开发中发现的问题作为 Bug 节点处理。

## M1：第一个可运行的 Agent — Anna

状态：`ACTIVE`

目标：应用能够启动 Anna；Agenty 按层级加载自身和 Anna 的设计，将任务交给独立 Runtime Machine，接收结果并完成一次受控收尾。

当前只确定第一个版本：

1. `v0.01`：Runtime Machine 公共模型与 OpenCode 底层适配。

第二个 API 版本已在 v0.01 验收后确定：

2. `v0.03`：Runtime 最小 Turn 调用链；先做公共状态机，再接 OpenCode JSON，最后增加显式真实冒烟测试。

第三个 API 版本继续完成 RuntimeMachine 底层：

3. `v0.05`：按应用侧六类职责，逐步完成 Runtime 类型与版本、事件归一化、会话、模型、交互、监控和结果管理。

当前推进到 `v0.05-d`：Runtime 类型/版本、公共事件流、Session + Environment binding、模型目录与 effort 校验均已完成自动回归。下一切片为 `v0.05-e` 交互管理，随后由 `v0.05-f` 完成监控与结果；v0.05 尚未整体完成。

后续版本只保留方向，不提前冻结范围和编号：

- 项目根目录基础能力与 Agenty Machine。
- Agent 层级加载。
- Anna 的定义、基础记忆与技能。
- 应用触发、双状态机协作和里程碑验收。

## 推进方式

M1 不采用一次性自顶向下实现，而采用双线交替：

```text
Runtime Machine 底层事实
        ↑       ↓
统一命令/事件协议
        ↑       ↓
Agenty Machine 顶层需要
```

每完成一个底层切片，就回到顶层验证是否足以表达 Agenty 的需要；每增加一个顶层状态，再回到底层验证 Runtime 是否能提供对应事件。两条线在 Anna 的完整执行链路交汇时完成 M1。
