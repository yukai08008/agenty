# agenty

[English](README.md)

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

# 运行 demo agent 任务
agenty run           # 默认：问候
agenty run greet     # 问候
agenty run think     # 深度思考
agenty run status    # 系统状态

# 启动交互式聊天
agenty chat

# 升级到最新版本
agenty upgrade

# 查看帮助
agenty --help
```

## 工作原理

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
