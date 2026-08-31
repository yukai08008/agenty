# v1.01 TEST_CASES — 多 Agent 生命周期与可恢复状态机

约定：

- U-xx：Python 单元测试
- C-xx：CLI 端到端测试
- G-xx：Git 与文件系统安全测试

## 0. 不变量回归

| ID | 范围 | 命令 |
| --- | --- | --- |
| I-01 | Python 3.10 | `uv run --python 3.10 python -m unittest discover -s tests -v` |
| I-02 | Python 3.14 | `uv run --python 3.14 python -m unittest discover -s tests -v` |
| I-03 | 格式与空白 | `git diff --check` |
| I-04 | Vault 关系 | `vault_tool.py check --strict knowledge` |
| I-05 | 构建 | `uv build` |
| I-06 | 运行时数据不进源码 Git | `git ls-files | rg '(^|/)(memory|sessions|agent_log\.jsonl)(/|$)'` 应无生成数据 |

## 1. Feature A — 控制面与状态机

| ID | 用例 | → acceptance | 自动化 |
| --- | --- | --- | --- |
| U-01 | 初始化隔离的 AGENTY_HOME | a-1 | 是 |
| U-02 | claim 两个 Agent，ID 与目录互不相同 | a-1 | 是 |
| U-03 | 名称冲突和非法 selector 被拒绝 | a-1 | 是 |
| U-04 | 生命周期与执行状态合法转移 | a-2 | 是 |
| U-05 | 非法转移不改变 revision | a-2 | 是 |
| U-06 | 删除/落后 current 后由 events 恢复 | a-3 | 是 |
| U-07 | checkpoint 保存 payload 并更新恢复指针 | a-4 | 是 |
| U-08 | 并发 checkpoint revision 唯一连续 | a-4 | 是 |

## 2. Feature B — Worker 与 suite

| ID | 用例 | → acceptance | 自动化 |
| --- | --- | --- | --- |
| U-09 | 默认 agents home 创建 Worker | b-1 | 是 |
| U-10 | 自定义路径创建 Worker | b-1 | 是 |
| U-11 | 非空路径和重复创建被拒绝 | b-1 | 是 |
| U-12 | suite 三文件三目录与基础 skill 完整 | b-2 | 是 |
| U-13 | snapshot 更新 MEMORY 并写 memory/session/log | b-3 | 是 |

## 3. Feature C — CLI、runtime 与迁移

| ID | 用例 | → acceptance | 自动化 |
| --- | --- | --- | --- |
| C-01 | init→claim→workspace→snapshot→checkpoint→show | c-1 | 是 |
| C-02 | list 同时展示 N 个 Agent | c-1 | 是 |
| C-03 | start --dry-run 输出 runtime 与工作目录 | c-2 | 是 |
| C-04 | 假 runtime 成功/失败均形成状态闭环 | c-2 | 是 |
| G-01 | WORKER→PROJECT 迁移保持 ID 和历史 | c-3 | 是 |
| G-02 | 迁移后源目录仍存在 | c-3 | 是 |
| G-03 | 非空目标、运行中迁移和子路径迁移被拒绝 | c-3 | 是 |
| G-04 | `--init-git` 创建有效仓库和 `.gitignore` | c-4 | 是 |

## 4. 部署验证

| ID | 用例 | → 部署检查 |
| --- | --- | --- |
| D-01 | wheel/sdist 可构建 | `uv build` 成功 |
| D-02 | wheel 安装后的 `agenty --help` | 所有第一批命令可见 |
| D-03 | 测试 home 隔离 | 用户真实 `~/.agenty` 未发生变化 |

## 5. 前端说明

v1.01 是 API 版，无 Web 交付，Web 测试和浏览器 e2e 不适用。v1.02 若增加界面，必须补齐对应测试。
