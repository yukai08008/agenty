# v0.01 TEST_CASES — Runtime Machine 与 OpenCode

## 0. 不变量

| ID | 用例 | 自动化 |
|---|---|---|
| INV-01 | 公共模型不出现 `opencode`、`codex`、`claude` 专属字段 | 是 |
| INV-02 | OpenCode 命令默认不含自动批准参数 | 是 |
| INV-03 | 自动测试不调用真实模型 | 是 |
| INV-04 | `git ls-files data/` 结果为空 | 是 |
| INV-05 | Runtime 跨边界与可持久化状态模型继承 Pydantic BaseModel | 是 |

## 1. v0.01-a Runtime 公共协议

| ID | 用例 | 验收 |
|---|---|---|
| PA-01 | Availability、Channel、Session、Turn 使用独立状态类型 | PA-1 |
| PA-02 | RuntimeEvent 携带 Runtime 和 correlation ID | PA-2 |
| PA-03 | RuntimeEvent 可选携带 Session 和 Turn ID | PA-2 |
| PA-04 | RuntimeSnapshot 同时表达四类独立状态 | PA-3 |
| PA-05 | 所有公共事件名称全局唯一 | PA-2 |
| PA-06 | 公共协议不存在厂商专属字段 | PA-4 |
| PA-07 | 未确认的 `CANCELLING/DELETING` 不进入当前基线 | PA-1 |

## 2. v0.01-b Capability 与 AvailabilityMachine

| ID | 用例 | 验收 |
|---|---|---|
| PB-01 | 初始状态为 `UNKNOWN` | PB-1 |
| PB-02 | 探测过程进入 `PROBING` | PB-1 |
| PB-03 | 成功探测进入 `AVAILABLE` | PB-1 |
| PB-04 | 缺失和不兼容使用不同状态 | PB-1 |
| PB-05 | Capability 记录版本、通道、证据和约束 | PB-2 |
| PB-06 | Runtime 协议模型可执行 JSON dump/validate 往返 | PB-3 |
| PB-07 | AvailabilityStateData 可持久化并恢复 Machine | PB-3 |
| PB-08 | Runtime 协议拒绝未声明字段 | PB-3 |

## 3. v0.01-c OpenCode Probe

| ID | 用例 | 验收 |
|---|---|---|
| PC-01 | 找到假 OpenCode 并解析版本 | PC-1 |
| PC-02 | 找不到可执行文件 | PC-2 |
| PC-03 | `--version` 超时 | PC-2 |
| PC-04 | `--version` 非零退出 | PC-2 |
| PC-05 | 记录能力来源、版本和通道 | PC-1/PC-3 |
| PC-06 | 版本格式错误与版本不支持均进入 `INCOMPATIBLE`，并使用不同失败代码 | PC-2 |
| PC-07 | 版本已确认但 help 探测失败时进入 `DEGRADED` | PC-2/PC-3 |
| PC-08 | help 参数只形成 `unknown/advertised` 记录 | PC-1/PC-3 |
| PC-09 | Probe 只调用 `--version` 和 `run --help`，不调用模型 | PC-1 |
