# v0.01 TEST_CASES — Runtime Machine 与 OpenCode

## 0. 不变量

| ID | 用例 | 自动化 |
|---|---|---|
| INV-01 | 公共模型不出现 `opencode`、`codex`、`claude` 专属字段 | 是 |
| INV-02 | OpenCode 命令默认不含自动批准参数 | 是 |
| INV-03 | 自动测试不调用真实模型 | 是 |
| INV-04 | `git ls-files data/` 结果为空 | 是 |

## 1. Runtime 公共模型

| ID | 用例 | 验收 |
|---|---|---|
| RM-01 | 初始状态为 `UNKNOWN` | RM-1 |
| RM-02 | `probe` 进入 `PROBING` | RM-1 |
| RM-03 | 成功探测进入 `READY` | RM-1 |
| RM-04 | 探测失败进入 `UNAVAILABLE` | RM-1 |
| RM-05 | 非法事件被拒绝且状态不变 | RM-1 |
| RM-06 | capability 不支持时明确拒绝 | RM-2 |

## 2. OpenCode Probe

| ID | 用例 | 验收 |
|---|---|---|
| OC-01 | 找到假 OpenCode 并解析版本 | OC-1 |
| OC-02 | 找不到可执行文件 | OC-2 |
| OC-03 | `--version` 超时 | OC-2 |
| OC-04 | `--version` 非零退出 | OC-2 |
| OC-05 | 记录能力来源和版本 | OC-1/AR-1 |

## 3. 顶层校准

| ID | 用例 | 验收 |
|---|---|---|
| AR-01 | READY 能触发未来的 runtime 可选事件 | AR-1 |
| AR-02 | UNAVAILABLE 能携带可展示的结构化原因 | AR-1 |
