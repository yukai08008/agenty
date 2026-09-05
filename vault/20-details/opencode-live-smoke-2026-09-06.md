---
id: opencode-live-smoke-2026-09-06
type: journal
status: active
updated: 2026-09-06
tags: [agenty, opencode, live-test, runtime, turn]
part_of:
  - "[[agenty-state-machines]]"
implements:
  - "[[runtime-turn-contract]]"
related:
  - "[[runtime-capability-scope]]"
---

# 2026-09-06 — OpenCode 1.18.26 live smoke

## Summary

v0.03-c 的显式 live case 已贯通真实 OpenCode 新 Session 调用。第一个 free 模型受到 provider 限流，第二个 free 模型成功返回固定文本；两条路径都正确驱动公共 Turn 状态机。

## Evidence

共同条件：

```text
runtime: OpenCode 1.18.26
channel: transient_process
workspace: /Users/andy/mycode/agenty
command shape: run --format json --dir <workspace> --model <model> -- <prompt>
tools requested by prompt: none
```

结果：

1. `opencode/mimo-v2.5-free` 创建 Session `ses_f8d7fcb25ffeM9R7ogTBfQIBrg`，provider 返回 HTTP 429 FreeUsageLimitError；Adapter 记录 `retryable=true`，Turn 为 `FAILED`。
2. `opencode/nemotron-3.5-lightning-free` 创建 Session `ses_f8d7e04baffetMP6TmhgpvgrA8`，约 7.4 秒返回 `AGENTY_SMOKE_OK`，Turn 为 `SUCCEEDED`。

## Scope

已验证：新 Session、显式 model、JSONL、Session ID、文本事件、Runtime error 和成功/失败终态。

未验证：effort、Session resume/fork、工具修改、审批、长期通道以及完整 Environment identity。项目 Git 状态未出现由 Runtime 造成的新修改。
