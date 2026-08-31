---
id: agent-suite
type: entity
status: active
updated: 2026-09-01
tags: [locate, agent-suite, workspace]
depends_on: "[[control-plane]]"
related:
  - "[[cli]]"
---

# agent-suite

## entry

- `src/agenty/suite.py` — suite 创建、校验、语义事件和 project-snapshot 场景
- `src/agenty/workspace.py` — Worker 创建与 Worker→Project 安全迁移

## reads

| 任务类型 | 必读（按顺序） |
| --- | --- |
| develop suite | `suite.py` → `test_suite.py` |
| develop workspace | `workspace.py` → `suite.py` → `test_workspace.py` |
| fix snapshot | `suite.py:create_project_snapshot` → `test_suite.py` |
| fix migration | `workspace.py:migrate_worker` → `test_workspace.py` |

## tests

- `tests/test_suite.py`
- `tests/test_workspace.py`

## symptoms

| 症状 | 先看 |
| --- | --- |
| MEMORY 与详细 memory 不一致 | `create_project_snapshot` |
| 本地状态被 Git 跟踪 | `GITIGNORE_ENTRIES`、`update_gitignore` |
| 迁移后 identity 改变 | `migrate_worker` binding 更新 |
| 非空目录被覆盖 | `_require_empty_target` |

## related

- 控制面与 suite 的职责边界见 [[decision-multi-agent-control-plane]]。
