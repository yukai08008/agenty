# v0.05 TEST_CASES — RuntimeMachine 六类职责回归

状态：先冻结全部回归范围；按 v0.05-a → f 顺序逐类实现。未实现的用例标记为“待实现”，不能被误报为通过。

## 0. 跨类不变量

| ID | 用例 | 状态 |
|---|---|---|
| INV-01 | 公共模型不存在 OpenCode、Codex、Claude 专属字段 | 已自动化 |
| INV-02 | 跨边界和持久化状态都是 Pydantic BaseModel | 已自动化 |
| INV-03 | 非法事件不改变状态或事件序列 | 已自动化 |
| INV-04 | Runtime、Session、Turn、correlation 上下文不能漂移 | 已自动化 |
| INV-05 | 默认测试不调用真实模型，auto 默认关闭 | 已自动化 |
| INV-06 | `git ls-files data/` 为空 | 质量门 |

## 1. Runtime 类型与版本

| ID | 回归用例 | 预期 | 状态 |
|---|---|---|---|
| RT-01 | 创建 RuntimeTarget | 类型和精确版本均为必填 | 已自动化 |
| RT-02 | 注册并选择完全匹配的 Adapter | `UNSELECTED → RESOLVING → SELECTED` | 已自动化 |
| RT-03 | Runtime 类型未注册 | 进入 `REJECTED`，不启动 Runtime | 已自动化 |
| RT-04 | 类型存在但目标版本未注册 | 进入 `REJECTED`，不能自动使用其他版本 | 已自动化 |
| RT-05 | Adapter 探测所得类型或版本与目标不同 | identity mismatch，拒绝选择 | 已自动化 |
| RT-06 | Runtime 不可用或不兼容 | 保留结构化 RuntimeFailure | 已自动化 |
| RT-07 | 已选择时再次选择 | 必须先 clear，非法命令不修改状态 | 已自动化 |
| RT-08 | StateData JSON 往返 | 可恢复并继续重试 | 已自动化 |

## 2. 事件归一化

| ID | 回归用例 | 预期 | 状态 |
|---|---|---|---|
| EV-01 | 已知厂商事件 | 转换为对应公共 RuntimeEvent | 已自动化 |
| EV-02 | 一次输出包含多个厂商事件 | 公共事件顺序稳定且 sequence 单调 | 已自动化 |
| EV-03 | 厂商事件携带 Session/Turn | 公共关联上下文完整 | 已自动化 |
| EV-04 | 未知事件类型 | 明确 unknown/invalid，不静默改变状态 | 已自动化 |
| EV-05 | 畸形 JSON 或字段 | 结构化 `invalid_output` | 已自动化 |
| EV-06 | raw event | 只作为诊断证据，公共 payload 不依赖厂商结构 | 已自动化 |

## 3. 会话管理

| ID | 回归用例 | 预期 | 状态 |
|---|---|---|---|
| SE-01 | 新建 Session | `NONE → RESOLVING → READY` | 已自动化 |
| SE-02 | 接续 Session | 必须显式 session ID 和 EnvironmentRef | 已自动化 |
| SE-03 | Session 不存在 | 进入 `FAILED` 并可重试 | 已自动化 |
| SE-04 | Environment identity 一致 | 允许接续 | 已自动化 |
| SE-05 | Environment identity 不一致 | 阻断接续，不调用 Runtime | 已自动化 |
| SE-06 | Turn 开始与结束 | Session 在 `READY ↔ BUSY` 转换 | 已自动化 |
| SE-07 | Session lineage | 新建/接续来源可追踪，并为后续 fork 保留 parent | 已自动化 |

## 4. 模型类型、模型标识与 effort

| ID | 回归用例 | 预期 | 状态 |
|---|---|---|---|
| MO-01 | 设置模型类型和模型标识 | 保存 desired selection | 已自动化 |
| MO-02 | 设置 effort | 与模型选择共同校验但不成为生命周期状态 | 已自动化 |
| MO-03 | Runtime 接受配置 | 有执行级证据后写入 effective selection | 已自动化 |
| MO-04 | 模型不存在或 effort 不支持 | 执行前结构化失败 | 已自动化 |
| MO-05 | Runtime 回报实际模型不同 | 不覆盖 desired，单独记录 effective | 已自动化 |
| MO-06 | 配置 JSON 往返 | desired/effective 可恢复 | 已自动化 |

## 5. 交互管理

| ID | 回归用例 | 预期 | 状态 |
|---|---|---|---|
| IN-01 | 默认策略 | `deny_by_default`，不出现隐式 auto | 已自动化 |
| IN-02 | ask 且通道支持授权 | Turn 进入 `WAITING_APPROVAL` | 已自动化 |
| IN-03 | approve/reject | 使用 request ID 恢复 Turn | 已自动化 |
| IN-04 | ask 但通道不支持 | 执行前被 capability guard 拒绝 | 已自动化 |
| IN-05 | 显式 auto_approve | Adapter 才能映射为 Runtime auto 参数 | 已自动化 |
| IN-06 | 自动或人工授权 | 决策主体、时间和结果进入审计事件 | 已自动化 |
| IN-07 | cancel/timeout | 进程被回收，Turn 到达对应终态 | 已自动化 |

## 6. 执行监控与结果管理

| ID | 回归用例 | 预期 | 状态 |
|---|---|---|---|
| RS-01 | HTTP 429 / FreeUsageLimit | `rate_limited`，保留 retryable | 已部分自动化 |
| RS-02 | 额度耗尽、认证失败、模型不可用 | 使用不同公共失败代码 | 待实现 |
| RS-03 | Runtime 崩溃、非零退出、超时 | 终态和失败原因一致 | 已部分自动化 |
| RS-04 | usage 事件 | 聚合 token、费用及 provider 原始引用 | 待实现 |
| RS-05 | 文件产物 | ArtifactManifest 包含路径、类型、大小、digest、producer | 待实现 |
| RS-06 | 事件日志 | EventLogRef 可定位归一化日志和原始证据 | 待实现 |
| RS-07 | TurnResult | 聚合状态、输出、usage、failure、artifacts 和日志 | 待实现 |
| RS-08 | 终态结果 JSON 往返 | 不可变、可持久化、可审计 | 待实现 |
