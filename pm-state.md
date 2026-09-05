# 项目状态: agenty

> 最近更新: 2026-09-05 | 更新者: Codex PM

## 里程碑

### M1 Anna (ACTIVE)

- 目标：完成第一个由应用触发、通过独立 Runtime 执行的层级化 Agent。

## 版本状态树

### v0.01 (CODE_COMPLETE) — Runtime 接入基线

- **v0.01-a Runtime 公共协议** (CODE_COMPLETE)
  - 分支：`v0.01-a`
  - 已定义 Availability、Channel、Session、Turn 四类独立状态
  - 已定义标准事件名称、RuntimeIdentity、RuntimeEvent 和聚合 RuntimeSnapshot
  - 质量门：15 项 pytest 通过、compileall 通过、diff check 通过、data 未被 Git 追踪
  - 工具缺口：项目未配置 ruff，未形成 lint 结论
- **v0.01-b Capability 与 AvailabilityMachine** (CODE_COMPLETE)
  - 分支：`v0.01-b`
  - Capability 已绑定 Runtime 版本、Channel、支持状态、证据和约束
  - AvailabilityMachine 已使用标准事件驱动，并区分 AVAILABLE、DEGRADED、UNAVAILABLE、INCOMPATIBLE
  - Runtime 协议模型与 AvailabilityStateData 已对齐 andybot，迁移为 Pydantic v2
  - **issue-pydantic-state-models** (CLOSED)：早期 dataclass 模型不符合项目约束，已迁移并增加 JSON 往返恢复测试
  - 质量门：30 项 pytest 通过、compileall 通过、diff check 通过、data 未被 Git 追踪
- **v0.01-c OpenCode 1.18.26 Probe** (CODE_COMPLETE)
  - 分支：`v0.01-c`
  - 通用 RuntimeProbeMachine 与版本绑定的 OpenCode Adapter 已分离
  - 失败已区分缺失、探测超时、命令退出、版本格式错误、版本不支持和内部异常
  - help 参数只形成 `support=unknown / evidence=advertised` 的能力记录
  - 本机 OpenCode 1.18.26 无模型探测结果为 `AVAILABLE`，发现 8 条 advertised 能力
  - **issue-capability-evidence-scope** (CLOSED)：旧 capability 集合与旧 RuntimeMachine 已移除
  - 质量门：30 项 pytest 通过、真实无副作用 probe 通过、data 未被 Git 追踪
  - 工具缺口：项目未安装 ruff，未形成 lint 结论

### v0.03 (CODE_COMPLETE) — Runtime 最小 Turn 调用链

- 父基线：`v0.01-c@80be93f`；v0.01 为不发布的 API 迭代，因此没有 final tag
- 跳过 v0.02：本阶段是协议和后端行为，不属于偶数 Web 版
- **v0.03-a 公共 Turn 协议与状态机** (CODE_COMPLETE)
  - 分支：`v0.03-a`
  - RuntimeTurnRequest 强制绑定 turn、correlation、prompt 和工作目录
  - TurnMachine 拒绝非法生命周期、错误事件域及 Runtime/Turn/Session 上下文漂移
  - TurnStateData 使用 Pydantic v2，可 JSON 往返并恢复 Machine
  - 质量门：47 项 pytest、compileall、diff check、vault strict 全部通过；data 未被 Git 追踪
  - 工具缺口：项目未安装 ruff，未形成 lint 结论
- **v0.03-b OpenCode 1.18.26 JSON 调用适配** (CODE_COMPLETE)
  - 分支：`v0.03-b`
  - RuntimeTurnRunner 只处理公共事件，OpenCode Adapter 隔离命令和 JSONL 细节
  - 当前只创建新 Session；工作目录同时绑定 cwd 与 `--dir`
  - prompt 置于 `--` 后，默认不含 auto、resume 或 fork 参数
  - 成功、Runtime error、tool error、非零退出、畸形 JSON、超时与目录缺失均有自动测试
  - 质量门：55 项 pytest、compileall、diff check、vault strict 全部通过；data 未被 Git 追踪
  - 真实模型尚未调用；项目仍未安装 ruff
- **v0.03-c 显式真实模型冒烟测试** (CODE_COMPLETE)
  - 分支：`v0.03-c`
  - 默认测试保持 skip，只有 `AGENTY_LIVE_OPENCODE=1` 才调用真实模型
  - `opencode/mimo-v2.5-free` 真实返回 HTTP 429，调用链正确记录 Session 和结构化失败
  - `opencode/nemotron-3.5-lightning-free` 真实调用成功，Session 为 `ses_f8d7e04baffetMP6TmhgpvgrA8`
  - live 验证覆盖新 Session、model、JSON、Session ID、文本输出和终态，不扩展到 effort/resume/fork
  - 真实 error 回归推动 Adapter 保留 message、status code 和 retryable，过滤 headers/body
  - 质量门：默认套件 55 passed / 1 live skipped；显式 live case 1 passed；compileall、diff check、vault strict 通过
  - 项目仍未安装 ruff

## 历史分支

- `feature/file-agent-foundation` (ABANDONED)：方向确认前过早实现；保留本地提交作为历史，不合并、不推送。
- `feature/runtime-machine-opencode`：v0.01 拆分前的工作基线；后续从 `v0.01-a` 继续按 Feature 推进。

## 当前焦点

- v0.03 调用链已贯通；下一步回到 AgentyMachine 顶层，校准它如何提交 RuntimeTurnRequest 和消费 Turn 结果。

## 已确认的后续设计约束

- 原生 Runtime Session fork 不足以表示完整执行分支。
- 执行分支必须同时锁定 Runtime Session lineage 和项目 Environment。
- 后续协议需要明确 `Env → Action(strategy) → Env' → Reward`，具体实现与版本排期尚未决定。

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
- [x] v0.01-b：落地 capability 的版本、通道、证据模型和 AvailabilityMachine
- [x] 修复状态模型实现约束：统一为 Pydantic v2
- [x] 将 OpenCode Probe 迁移到 v0.01-b 公共模型
- [ ] 再推进 OpenCode 配置与会话切片
- [x] v0.03-a：实现公共 Turn 请求、状态数据和状态机
- [x] v0.03-b：实现 OpenCode JSON 调用适配
- [x] v0.03-c：增加显式开启的真实模型冒烟测试

## 不变量

- 里程碑由若干版本完成，不能把里程碑等同于版本。
- 顶层与底层任务交替推进，在 Anna 完整链路处交汇。
- RuntimeMachine 与 AgentyMachine 不共享内部状态。
- OpenCode 是首个实现，不是公共协议本身。
