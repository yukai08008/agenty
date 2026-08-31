# v1.01 TEST_CASES_FINAL — POC 验收记录

> 验收日期：2026-09-01  
> 验收分支：`v1.01`  
> 验收提交：`9050432` 及其工作树中的本验收记录

## 结论

v1.01 POC 通过。计划中的 20 个自动化测试全部通过，构建、安装、知识库关系、源码清洁与安装脚本语法门禁均通过。该版本是奇数 API 开发版，不打正式发布 tag。

## 自动化测试结果

| 测试集 | Python 3.10 | Python 3.14 | 结果 |
| --- | ---: | ---: | --- |
| store / 多 Agent 隔离与权限 | 3/3 | 3/3 | PASS |
| state / 转移、恢复、checkpoint、并发与任务上下文 | 6/6 | 6/6 | PASS |
| runtime / dry-run、成功与失败闭环 | 3/3 | 3/3 | PASS |
| suite / 结构、快照与完整性检查 | 3/3 | 3/3 | PASS |
| workspace / Worker 创建与安全迁移 | 4/4 | 4/4 | PASS |
| CLI / 生命周期端到端 | 1/1 | 1/1 | PASS |
| **合计** | **20/20** | **20/20** | **PASS** |

测试覆盖 `TEST_CASES.md` 中的 U-01～U-13、C-01～C-04 与 G-01～G-04。CLI 端到端用例实际贯穿 `init → claim → workspace create → snapshot → checkpoint → show → migrate`，并验证多 Agent 列表和 Git 初始化结果。

## 质量门禁

| 门禁 | 命令/检查 | 结果 |
| --- | --- | --- |
| Python 3.10 回归 | `uv run --python 3.10 python -m unittest discover -s tests -v` | PASS，20 tests |
| Python 3.14 回归 | `uv run --python 3.14 python -m unittest discover -s tests -v` | PASS，20 tests |
| Knowledge Vault | `vault_tool.py check --strict knowledge` | PASS，8 notes / 0 errors / 0 warnings |
| Python 编译 | `python -m compileall src tests` | PASS |
| 安装脚本语法 | `bash -n install.sh` | PASS |
| Git 空白检查 | `git diff --check` | PASS |
| 构建 | `uv build` | PASS，wheel 与 sdist |
| wheel 启动 | `uvx --from ./dist/agenty-0.1.0-py3-none-any.whl agenty --version` | PASS，输出 `0.1.0` |
| 运行数据隔离 | 检查 Git 跟踪文件中的 memory/session/log 运行数据 | PASS，无生成数据进入源码 |

## 验收说明

- v1.01 不含 Web，浏览器 e2e 不适用。
- `ruff` 临时工具下载两次超时，未作为本版阻断项；代码已通过编译、测试、空白检查和人工行宽检查。
- 测试使用隔离的临时 `AGENTY_HOME`，没有改动用户真实的 `~/.agenty`。
- Python 包版本暂为 `0.1.0`，与项目管理 API 版本 `v1.01` 分开；映射策略留到 v1.02 正式版决定。

## 暂不纳入本版

- Codex、OpenCode、Claude 的深度 session adapter 与恢复协议
- daemon、trigger 调度和消息通道
- 同一个 Git 项目内多个 agent suite 的命名与隔离规范
- Web 管理界面、远程控制面和正式发布/升级策略
