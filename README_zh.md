# agenty

[English](README.md)

> 项目正在从早期 demo CLI 演进为具有推理、记忆与多 Runtime 接入能力的 Agent 系统。`agenty run` 现已暴露 OpenCode 1.18.26 RuntimeMachine 底座，但还不是完整的 Anna Agent。总体目标见 [`ROADMAP.md`](ROADMAP.md)，当前进度见 [`pm-state.md`](pm-state.md)，历史变化见 [`CHANGELOG.md`](CHANGELOG.md)，接手规范见 [`AGENTS.md`](AGENTS.md)。

基于 uv 构建的 demo agent CLI —— 演示如何创建一个 Linux 和 macOS 上一行命令安装的 Python CLI 工具。

## 一键安装

```bash
curl -fsSL https://raw.githubusercontent.com/yukai08008/agenty/main/install.sh | bash
```

## 卸载

```bash
curl -fsSL https://raw.githubusercontent.com/yukai08008/agenty/main/install.sh | bash -s -- uninstall
```

## 使用 uv 直接安装

如果你已经安装了 [uv](https://docs.astral.sh/uv/)：

```bash
uv tool install git+https://github.com/yukai08008/agenty.git
```

## 使用方法

```bash
# 查看版本和系统信息
agenty --version

# 打招呼
agenty hello
agenty hello Alice

# 使用精确 OpenCode 1.18.26 执行自然语言任务
agenty run "总结这个仓库"

# 为本次 Turn 显式允许非交互工具执行
agenty run "只读检查磁盘使用情况" --auto-approve

# 绑定其他工作目录并输出完整 TurnResult JSON
agenty run "审查这个项目" -C /path/to/project --json

# 启动交互式聊天
agenty chat

# 升级到最新版本
agenty upgrade

# 查看帮助
agenty --help
```

## 工作原理

`agenty run` 会选择精确 OpenCode 1.18.26、探测能力、构造 RuntimeTurnRequest，并返回包含终态、输出、Session、usage、文件变化观察以及 normalized/raw 证据日志引用的 TurnResult。除非显式传入 `--auto-approve`，否则不会打开工具自动批准。

当前命令只是最小 Runtime 应用入口。AgentyMachine、Anna 身份、分层记忆/技能和长期结果存储仍在开发中。

可运行 `agenty run --help` 查看超时、OpenCode 路径、工作目录和 JSON 输出选项。

## 安装原理

安装脚本（`install.sh`）做三件事：

1. **安装 uv**（如果尚未安装）—— 快速 Python 包管理器
2. **确保 `~/.local/bin` 在 PATH 中** —— 标准的用户级 bin 目录
3. **通过 `uv tool install` 安装 agenty** —— 隔离环境，无依赖冲突

由于 Python 源码跨平台，uv 自动处理虚拟环境，同一份脚本在 Linux 和 macOS 上完全一致，无需任何平台特定逻辑。

## 项目结构

```
agenty/
├── install.sh          # 一键安装脚本
├── pyproject.toml      # 项目配置 + CLI 入口
├── README.md           # 英文文档
├── README_zh.md        # 中文文档
└── src/
    └── agenty/
        ├── __init__.py  # 版本号
        └── cli.py       # CLI 命令
```

## 开发

```bash
# 克隆
git clone https://github.com/yukai08008/agenty.git
cd agenty

# 直接运行（无需安装）
uvx --from . agenty --version

# 或本地安装
uv tool install --force .
```
