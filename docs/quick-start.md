# Hermes Agent 快速上手指南

欢迎使用 Hermes Agent！本指南将帮助你在 10 分钟内启动并运行 Hermes Agent。

---

## 目录

1. [前置要求](#前置要求)
2. [安装](#安装)
3. [首次配置](#首次配置)
4. [开始对话](#开始对话)
5. [常用命令](#常用命令)
6. [配置消息网关](#配置消息网关)
7. [设置定时任务](#设置定时任务)
8. [创建技能](#创建技能)
9. [下一步](#下一步)

---

## 前置要求

在开始之前，请确保你的系统满足以下要求：

### 系统要求

| 要求 | 说明 |
|------|------|
| **操作系统** | Linux、macOS、WSL2（Windows 原生不支持） |
| **Python** | 3.11 或更高版本 |
| **Node.js** | 18 或更高版本（用于部分功能） |
| **内存** | 建议 4GB+ |
| **磁盘空间** | 建议 10GB+ |

### API 密钥

你需要至少一个 LLM 提供商的 API 密钥。以下是推荐选项：

| 提供商 | 说明 | 获取地址 |
|--------|------|----------|
| OpenRouter | 支持 200+ 模型，推荐 | https://openrouter.ai/keys |
| Anthropic Claude | 原生支持，性能好 | https://console.anthropic.com/ |
| OpenAI | GPT-4/GPT-3.5 | https://platform.openai.com/api-keys |
| Google Gemini | 快速且经济 | https://aistudio.google.com/app/apikey |

---

## 安装

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

如果你想手动安装，请按以下步骤操作：

```bash
# 1. 克隆仓库
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent

# 2. 安装 uv（现代 Python 包管理器）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. 创建虚拟环境并安装依赖
uv venv venv --python 3.11
source venv/bin/activate
uv pip install -e ".[all,dev]"

# 4. 创建符号链接（可选，方便全局调用）
ln -s $(pwd)/hermes ~/.local/bin/hermes
```

### 验证安装

运行以下命令验证安装是否成功：

```bash
hermes --help
```

如果看到帮助信息，说明安装成功！

---

## 首次配置

### 1. 运行设置向导

首次运行 Hermes 时，建议使用设置向导：

```bash
hermes setup
```

该向导将引导你完成所有必要的配置。

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

**推荐配置（使用 OpenRouter）：**

```env
# OpenRouter - 支持 200+ 模型
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**其他可选配置：**

```env
# Anthropic 原生
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx

# Google AI Studio / Gemini
GOOGLE_API_KEY=xxxxxxxxxxxxxxxx

# OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 3. 选择默认模型

```bash
hermes model
```

这将打开一个交互式菜单，让你选择默认的模型和提供商。

**推荐模型：**
- `anthropic/claude-opus-4.6` - 最强大的模型，适合复杂任务
- `anthropic/claude-sonnet-4.6` - 平衡性能和成本
- `google/gemini-3-flash-preview` - 快速且经济实惠

### 4. 配置工具

```bash
hermes tools
```

这将让你选择启用哪些工具。建议启用：

| 工具 | 说明 |
|------|------|
| `terminal` | 终端访问（非常有用） |
| `file` | 文件操作 |
| `web` | Web 搜索和内容提取 |
| `skills` | 技能系统 |
| `todo` | 任务规划 |
| `memory` | 记忆工具 |

**安全提示：** 对于 `terminal` 等敏感工具，建议启用审批模式。

---

## 开始对话

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

| 命令 | 说明 |
|------|------|
| `/help` | 显示可用命令 |
| `/new` 或 `/reset` | 开始新对话 |
| `/model` | 切换模型 |
| `/personality` | 切换人格 |
| `/skills` | 查看技能 |
| `/compress` | 压缩对话上下文 |
| `/usage` | 查看使用统计 |
| `/insights` | 查看洞察分析 |
| `/verbose` | 切换详细输出 |
| `/stop` | 停止当前操作（在消息平台中） |

---

## 常用命令

### 基础命令

```bash
# 启动交互式 TUI 对话
hermes

# 选择模型
hermes model

# 配置工具
hermes tools

# 查看配置
hermes config list

# 设置配置项
hermes config set model.default anthropic/claude-sonnet-4.6

# 运行配置向导
hermes setup

# 诊断环境问题
hermes doctor

# 更新到最新版本
hermes update
```

### 配置管理

```bash
# 列出所有配置
hermes config list

# 获取配置值
hermes config get model.default

# 设置配置值
hermes config set model.default anthropic/claude-sonnet-4.6
hermes config set tools.terminal.enabled true

# 编辑配置文件
hermes config edit
```

### 模型管理

```bash
# 交互式选择模型
hermes model

# 直接设置模型
hermes model set anthropic/claude-sonnet-4.6

# 列出可用模型
hermes model list
```

### 工具管理

```bash
# 交互式配置工具
hermes tools

# 启用工具
hermes tools enable terminal
hermes tools enable file

# 禁用工具
hermes tools disable browser

# 列出工具状态
hermes tools list
```

---

## 配置消息网关

消息网关允许你通过 Telegram、Discord、Slack 等平台与 Hermes 对话。

### 1. 配置网关

```bash
hermes gateway setup
```

这将引导你配置各个平台。

### 2. Telegram 配置示例

1. 在 Telegram 中与 [@BotFather](https://t.me/BotFather) 对话
2. 发送 `/newbot` 创建新机器人
3. 按照提示获取 bot token
4. 配置 Hermes：

```yaml
# ~/.hermes/config.yaml
telegram:
  enabled: true
  token: "123456789:ABCdefGhIJKlmNoPQRStUvWxYz123456"
  home_channel: "123456789"  # 你的用户 ID（可选）
  reply_to_mode: "first"  # off/first/all
  require_mention: false  # 群聊中是否需要 @ 提及
  gateway_restart_notification: true
```

或者使用环境变量：

```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRStUvWxYz123456"
export TELEGRAM_HOME_CHANNEL="123456789"
```

### 3. Discord 配置示例

1. 访问 [Discord 开发者门户](https://discord.com/developers/applications)
2. 创建新应用
3. 添加 Bot
4. 复制 Bot Token
5. 配置 Hermes：

```yaml
# ~/.hermes/config.yaml
discord:
  enabled: true
  token: "YOUR_DISCORD_BOT_TOKEN_HERE"
  require_mention: false
  channel_skill_bindings:
    - id: "123456789012345678"
      skills: ["weather", "news"]
```

### 4. 启动网关

```bash
# 启动网关（前台运行）
hermes gateway start

# 启动网关（后台运行）
hermes gateway start --daemon

# 查看网关状态
hermes gateway status

# 停止网关
hermes gateway stop
```

### 5. 网关常用命令

```bash
# 设置网关
hermes gateway setup

# 启动网关
hermes gateway start

# 停止网关
hermes gateway stop

# 查看状态
hermes gateway status

# 查看日志
hermes gateway logs

# 重启网关
hermes gateway restart
```

---

## 设置定时任务

定时任务允许你自动化工作流。

### 1. 创建定时任务

在对话中使用 `/cronjob create` 命令：

```
You: /cronjob create

 🪽 Hermes: 让我们创建一个新的定时任务！

请提供以下信息：

1. 任务名称（例如："日报"）
2. Cron 表达式（例如："0 9 * * 1-5" 表示工作日早 9 点）
3. 要执行的操作（提示词/技能/命令）
4. 投递目标（origin/local/平台:聊天ID）
```

### 2. 示例：每日报告任务

```yaml
# ~/.hermes/cron/jobs.yaml
jobs:
  - id: daily-report
    name: 日报
    description: 生成每日工作摘要
    schedule: '0 9 * * 1-5'
    timezone: Asia/Shanghai
    enabled: true
    
    action:
      type: prompt
      content: |
        请分析今天的工作内容：
        1. 查看 git 历史
        2. 查看文件变更
        3. 生成工作摘要报告
        格式要求：Markdown，包含任务列表、进度、明天计划
    
    delivery:
      - 'telegram:123456789'
```

### 3. Cron 表达式快速参考

| 表达式 | 说明 |
|--------|------|
| `* * * * *` | 每分钟 |
| `*/5 * * * *` | 每 5 分钟 |
| `0 * * * *` | 每小时 |
| `0 9 * * *` | 每天早 9 点 |
| `0 9 * * 1-5` | 工作日早 9 点 |
| `0 9 1 * *` | 每月 1 号早 9 点 |
| `0 9 * * 1` | 每周一早 9 点 |

### 4. Cron 管理命令

```bash
# 列出所有定时任务
hermes cron list

# 创建新任务
hermes cron create --name "日报" --schedule "0 9 * * 1-5"

# 编辑任务
hermes cron edit daily-report

# 启用/禁用任务
hermes cron enable daily-report
hermes cron disable daily-report

# 立即执行任务
hermes cron run daily-report --now

# 查看任务日志
hermes cron logs daily-report

# 删除任务
hermes cron delete daily-report
```

---

## 创建技能

技能允许你保存和复用复杂的工作流。

### 1. 自动创建技能

Hermes 可以从你的对话中自动学习并创建技能：

```
You: /create-skill

 🪽 Hermes: 我可以帮你创建一个新技能！

我们可以：
1. 从最近的对话中学习模式
2. 基于模板创建
3. 从头开始创建

你想要哪种方式？

You: 从最近的对话中学习
```

### 2. 手动创建技能

```bash
# 创建技能目录
mkdir -p ~/.hermes/skills/my-skill
cd ~/.hermes/skills/my-skill
```

创建 `skill.yaml`：

```yaml
name: my-skill
version: 1.0.0
description: 我的第一个技能
author: Your Name
category: productivity
tags: [example, demo]

requirements:
  dependencies: []
  env_vars: []

commands:
  - name: main
    description: 主命令
    parameters:
      - name: topic
        type: string
        required: true
        description: 要研究的主题
    handler: main_handler

examples:
  - title: 研究示例
    content: /my-skill Python 编程
```

创建 `prompt.md`：

```markdown
你是一个专业的研究员。当用户询问某个主题时，请：

1. 先搜索相关信息
2. 整理关键要点
3. 提供资源链接
4. 给出学习建议

请使用 Markdown 格式输出，保持专业但友好的语气。
```

### 3. 使用技能

在对话中：

```
You: /my-skill Python 编程

 🪽 Hermes: [执行技能，研究 Python 编程主题...]
```

### 4. 技能管理命令

```bash
# 列出所有技能
hermes skills list

# 查看技能详情
hermes skills show my-skill

# 编辑技能
hermes skills edit my-skill

# 删除技能
hermes skills delete my-skill

# 从技能中心安装
hermes skills install community-skill
```

---

## 下一步

现在你已经成功启动并运行了 Hermes Agent！接下来可以探索：

### 1. 深入学习

- **阅读配置文档**：[configuration.md](./configuration.md) - 了解所有配置选项
- **学习技能系统**：查看技能相关文档和示例
- **探索工具系统**：尝试各种内置工具
- **理解记忆系统**：配置和使用记忆功能

### 2. 扩展功能

- **配置更多平台**：添加 Discord、Slack、微信等
- **设置更多定时任务**：自动化你的工作流
- **创建自定义技能**：保存和复用你的工作流
- **集成 MCP 服务器**：连接外部工具和服务

### 3. 为开发做准备

如果你想为 Hermes 做贡献：

- 阅读 [开发者指南](./developer-guide.md)
- 查看 [架构文档](./architecture/overview.md)
- 加入 [Discord 社区](https://discord.gg/NousResearch)

### 4. 推荐阅读

- [技术调研报告](./technical-research-report.md) - 深入了解技术架构
- [架构设计文档](./architecture-design.md) - 系统架构详解
- [最佳实践](./best-practices.md) - 使用技巧和注意事项
- [部署指南](./deployment.md) - 生产环境部署

---

## 故障排除

### 常见问题

#### 1. 安装失败

```bash
# 尝试运行诊断
hermes doctor

# 检查 Python 版本
python --version

# 确保 pip 是最新的
uv pip install --upgrade pip
```

#### 2. API 密钥问题

```bash
# 确认 .env 文件存在
ls -la ~/.hermes/.env

# 检查环境变量
echo $OPENROUTER_API_KEY

# 重新设置配置
hermes config edit
```

#### 3. 网关无法启动

```bash
# 查看日志
hermes gateway logs

# 检查端口占用
lsof -i :端口号

# 验证配置
hermes gateway setup
```

#### 4. 工具执行失败

```bash
# 检查工具是否启用
hermes tools list

# 查看审批设置
hermes config get tools.approval

# 检查执行环境
hermes doctor
```

### 获取帮助

如果遇到问题：

1. 运行 `hermes doctor` 诊断环境
2. 查看 [最佳实践](./best-practices.md) 中的常见问题
3. 访问 [GitHub Issues](https://github.com/NousResearch/hermes-agent/issues)
4. 加入 [Discord 社区](https://discord.gg/NousResearch)

---

## 快速参考卡

### 最常用命令

```bash
hermes                    # 开始对话
hermes model              # 选择模型
hermes tools              # 配置工具
hermes gateway start      # 启动网关
hermes setup              # 设置向导
hermes doctor             # 诊断问题
```

### 对话中常用命令

```
/help          # 帮助
/new           # 新对话
/model         # 切换模型
/skills        # 查看技能
/stop          # 停止操作
/insights      # 查看洞察
```

### 文件位置

| 路径 | 说明 |
|------|------|
| `~/.hermes/` | 用户数据目录 |
| `~/.hermes/config.yaml` | 主配置文件 |
| `~/.hermes/.env` | 环境变量 |
| `~/.hermes/skills/` | 用户技能目录 |
| `~/.hermes/sessions/` | 会话历史 |
| `~/.hermes/cron/` | 定时任务 |
| `~/.hermes/hooks/` | 事件钩子 |

---

祝你使用 Hermes Agent 愉快！🚀

如有任何问题，欢迎访问我们的 [GitHub](https://github.com/NousResearch/hermes-agent) 或加入 [Discord 社区](https://discord.gg/NousResearch)。

---

**相关文档：**
- [技术调研报告](./technical-research-report.md)
- [架构设计文档](./architecture-design.md)
- [配置文档](./configuration.md)
- [部署指南](./deployment.md)
- [开发者指南](./developer-guide.md)
- [最佳实践](./best-practices.md)
