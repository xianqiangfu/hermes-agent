# Hermes Agent 入门指南

欢迎使用 Hermes Agent！本指南将帮助你快速上手这个自进化 AI 代理。

## 目录

- [什么是 Hermes Agent](#什么是-hermes-agent)
- [前置要求](#前置要求)
- [快速安装](#快速安装)
- [初次配置](#初次配置)
- [第一个对话](#第一个对话)
- [常用命令](#常用命令)
- [下一步](#下一步)

## 什么是 Hermes Agent

Hermes Agent 是由 Nous Research 构建的自进化 AI 代理。它具有以下特性：

- 🧠 **闭环学习** - 从经验中创建技能，在使用中改进技能
- 💬 **多平台支持** - CLI、Telegram、Discord、Slack、WhatsApp 等
- 🔧 **强大工具集** - 终端、文件操作、浏览器自动化、Web 搜索等
- ⏰ **定时任务** - 内置 cron 调度器
- 🚀 **随处运行** - 本地、Docker、SSH、Modal、Daytona 等

## 前置要求

在安装 Hermes Agent 之前，请确保你的系统满足以下要求：

- **操作系统**：Linux、macOS、WSL2（Windows 原生不支持）
- **Python**：3.11 或更高版本
- **Node.js**：18 或更高版本（用于某些功能）
- **API 密钥**：至少一个 LLM 提供商的 API 密钥（推荐 OpenRouter）

## 快速安装

### 方法一：一键安装（推荐）

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

安装完成后，重新加载你的 shell 配置：

```bash
# 如果你使用 bash
source ~/.bashrc

# 如果你使用 zsh
source ~/.zshrc
```

### 方法二：手动安装

如果你想手动安装，可以按照以下步骤：

```bash
# 1. 克隆仓库
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent

# 2. 安装 uv（Python 包管理器）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. 创建虚拟环境并安装依赖
uv venv venv --python 3.11
source venv/bin/activate
uv pip install -e ".[all,dev]"

# 4. 创建符号链接（可选，方便全局调用）
ln -s $(pwd)/hermes ~/.local/bin/hermes
```

### 验证安装

安装完成后，运行以下命令验证安装：

```bash
hermes --help
```

如果看到帮助信息，说明安装成功！

## 初次配置

### 1. 运行配置向导

首次运行 Hermes 时，建议使用配置向导：

```bash
hermes setup
```

这将引导你完成所有必要的配置。

### 2. 配置 API 密钥

复制示例环境变量文件：

```bash
cp .env.example ~/.hermes/.env
```

然后编辑 `~/.hermes/.env` 文件，添加你的 API 密钥：

```bash
# 编辑文件
nano ~/.hermes/.env
```

**推荐配置**（使用 OpenRouter）：

```env
# OpenRouter - 支持 200+ 模型
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

**其他可选配置**：

```env
# Anthropic 原生
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Google AI Studio / Gemini
GOOGLE_API_KEY=your_google_api_key_here

# OpenAI
OPENAI_API_KEY=your_openai_api_key_here
```

获取 API 密钥：
- OpenRouter：https://openrouter.ai/keys
- Anthropic：https://console.anthropic.com/
- Google AI Studio：https://aistudio.google.com/app/apikey
- OpenAI：https://platform.openai.com/api-keys

### 3. 选择默认模型

```bash
hermes model
```

这将打开一个交互式菜单，让你选择默认的模型和提供商。

**推荐模型**：
- `anthropic/claude-opus-4.6` - 最强大的模型，适合复杂任务
- `anthropic/claude-sonnet-4.6` - 平衡性能和成本
- `google/gemini-3-flash-preview` - 快速且经济实惠

### 4. 配置工具

```bash
hermes tools
```

这将让你选择启用哪些工具。建议启用：
- `terminal` - 终端访问
- `file` - 文件操作
- `web` - Web 搜索和内容提取
- `skills` - 技能系统
- `todo` - 任务规划

## 第一个对话

### 启动 CLI

```bash
hermes
```

你会看到一个欢迎界面，然后可以开始对话。

### 示例对话

```
╭──────────────────────────────────────────────────────────────────────────────╮
│  🪽 Hermes Agent                                                            │
│  ──────────────────────────────────────────────────────────────────────────  │
│  Available Tools: terminal, file, web, skills, todo                         │
│  Available Skills: 0 loaded, 0 in ~/.hermes/skills/                         │
╰──────────────────────────────────────────────────────────────────────────────╯

Welcome! I'm Hermes, your AI assistant. I can help you with coding, research,
and many other tasks. Type /help for available commands.

You: 你好！能帮我创建一个 Python 脚本吗？

 🪽 Hermes: 你好！当然可以。我很乐意帮你创建 Python 脚本。

请告诉我：
1. 你想要这个脚本做什么？
2. 有什么特定的功能需求吗？

同时，我可以先查看当前目录的情况，了解你的工作环境。

You: 创建一个简单的 Hello World 脚本
```

### 使用斜杠命令

在对话中，你可以使用斜杠命令：

- `/help` - 显示可用命令
- `/new` 或 `/reset` - 开始新对话
- `/model` - 切换模型
- `/personality` - 切换人格
- `/skills` - 查看技能
- `/compress` - 压缩对话上下文
- `/verbose` - 切换详细输出
- `/stop` - 停止当前操作（在消息平台中）

## 常用命令

### 基础命令

```bash
# 启动交互式 CLI
hermes

# 选择模型
hermes model

# 配置工具
hermes tools

# 查看配置
hermes config list

# 设置配置项
hermes config set model.default anthropic/claude-opus-4.6

# 运行配置向导
hermes setup

# 检查环境
hermes doctor

# 更新到最新版本
hermes update
```

### 消息网关命令

```bash
# 配置消息网关
hermes gateway setup

# 启动消息网关
hermes gateway start

# 停止消息网关
hermes gateway stop

# 查看网关状态
hermes gateway status
```

### 定时任务命令

```bash
# 管理定时任务（在对话中使用）
/cronjob list
/cronjob create
/cronjob update
/cronjob pause
/cronjob resume
/cronjob remove
```

## 下一步

现在你已经成功启动并运行了 Hermes Agent！接下来可以探索：

1. **阅读配置文档** - 查看 [configuration.md](./configuration.md) 了解所有配置选项
2. **学习技能系统** - 了解如何创建和使用技能
3. **配置消息平台** - 在 Telegram、Discord 等平台上使用 Hermes
4. **尝试浏览器自动化** - 使用浏览器工具进行网页交互
5. **设置定时任务** - 创建自动化工作流

### 推荐阅读

- [配置文档](./configuration.md) - 详细的配置说明
- [部署文档](./deployment.md) - 各种部署方式
- [开发者指南](./developer-guide.md) - 如果你想为 Hermes 做贡献
- [API 文档](./api-docs.md) - 核心 API 说明
- [最佳实践](./best-practices.md) - 使用技巧和注意事项

## 获取帮助

如果遇到问题：

1. 运行 `hermes doctor` 检查环境
2. 查看 [最佳实践](./best-practices.md) 中的常见问题
3. 访问 GitHub Issues：https://github.com/NousResearch/hermes-agent/issues
4. 加入 Discord 社区：https://discord.gg/NousResearch

祝你使用 Hermes Agent 愉快！🚀
