# Agenty Machine 设计草案

## 当前设计范围

本文件按 RuntimeMachine 的已验证事实逐步展开，而不是一次定义完整顶层状态机。

## 第一次顶层校准：解析 Runtime

OpenCode `probe` 已能提供：

- Runtime 是否可用；
- Runtime 标识和版本；
- 可验证的公共能力集合；
- 不可用时的结构化失败原因。

因此 AgentyMachine 在加载具体 Agent 之前，需要一个明确的 Runtime 解析阶段：

```text
EMPTY
  → LOADING_BASE
  → RESOLVING_RUNTIME
      ├── runtime_accepted → LOADING_AGENT（后续版本）
      └── runtime_rejected → BLOCKED

BLOCKED
  ├── retry_runtime → RESOLVING_RUNTIME
  └── close → CLOSED
```

### `RESOLVING_RUNTIME` 的职责

1. 根据根配置选择 Runtime，例如默认 `opencode`。
2. 请求对应 RuntimeMachine 执行 `probe`。
3. 读取公共 `RuntimeSnapshot`，不读取 OpenCode 私有对象。
4. 使用当前任务所需能力做守卫检查。
5. 接受后只保存 Runtime 引用、版本和能力快照。

### 守卫

`runtime_acceptable` 至少检查：

- RuntimeMachine 状态为 `READY`；
- Runtime ID 与配置选择一致；
- 版本满足适配器支持范围；
- 当前阶段所需 capability 全部存在。

守卫失败时 Agenty 进入 `BLOCKED`，并保留 RuntimeMachine 提供的结构化原因。Agenty 不把 Runtime 的 `UNAVAILABLE` 复制成自己的同名状态。

## 第一次交汇结论

```text
AgentyMachine.RESOLVING_RUNTIME
            │ probe command
            ▼
RuntimeMachine.UNKNOWN → PROBING → READY / UNAVAILABLE
            │ RuntimeSnapshot
            ▼
Agenty runtime_accepted / runtime_rejected
```

这个交汇点已经足以指导下一底层切片：RuntimeMachine 需要增加配置上下文，并验证模型与 effort 能否设置；暂时还不需要创建 Session。
