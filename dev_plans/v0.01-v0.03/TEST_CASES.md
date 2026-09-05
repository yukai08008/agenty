# v0.03 TEST_CASES — Runtime 最小 Turn 调用链

## 0. 不变量回归

| ID | 范围 | 命令 |
|---|---|---|
| INV-01 | 全量 Python 回归 | `uv run pytest -q` |
| INV-02 | 公共协议无厂商字段 | `tests/test_runtime_protocol.py` |
| INV-03 | 自动测试不调用模型 | live case 默认 skip |
| INV-04 | 运行数据未被追踪 | `test -z "$(git ls-files data/)"` |
| INV-05 | Python 可编译 | `uv run python -m compileall -q src tests` |

## 1. v0.03-a 公共 Turn 协议与状态机

| ID | 用例 | 验收 | 自动化 |
|---|---|---|---|
| PA-01 | 请求拒绝空 prompt、空工作目录和空关联 ID | PA-1 | 是 |
| PA-02 | 创建、提交、接受、成功形成合法状态序列 | PA-2 | 是 |
| PA-03 | 输出事件只在 RUNNING 或等待状态接收且不改变生命周期 | PA-2 | 是 |
| PA-04 | 非法事件、Runtime/Turn/关联 ID 不匹配时不修改状态 | PA-2 | 是 |
| PA-05 | 失败和超时保存结构化失败原因 | PA-2 | 是 |
| PA-06 | TurnStateData JSON 往返后可恢复 Machine | PA-3 | 是 |
| PA-07 | 新公共字段不包含 OpenCode 专属概念 | PA-4 | 是 |

## 2. v0.03-b OpenCode JSON 调用适配

| ID | 用例 | 验收 | 自动化 |
|---|---|---|---|
| PB-01 | 假 Runtime 成功产生文本、Session ID 和 SUCCEEDED | PB-1/PB-3 | 是 |
| PB-02 | JSON error、畸形 JSON、非零退出和超时分别失败 | PB-2 | 是 |
| PB-03 | 命令固定使用 json 格式和指定工作目录 | PB-4 | 是 |
| PB-04 | 命令不含 `--auto`、resume 或 fork | PB-4 | 是 |

## 3. v0.03-c 显式真实冒烟测试

| ID | 用例 | 验收 | 自动化 |
|---|---|---|---|
| PC-01 | 未设置 live 开关时跳过 | PC-1 | 是 |
| PC-02 | 显式开启后完成一次最小真实 Turn | PC-2 | 条件执行 |
| PC-03 | 证据只对应实际 Runtime 版本、通道和能力 | PC-3 | 条件执行 |
