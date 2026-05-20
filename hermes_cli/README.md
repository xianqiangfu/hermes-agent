# Hermes CLI 命令行模块

Hermes CLI 是 Hermes Agent 的统一命令行接口，提供与 AI 代理交互的所有功能。

## 目录

- [架构概览](#架构概览)
- [核心组件](#核心组件)
- [命令列表](#命令列表)
- [使用示例](#使用示例)
- [命令行参数](#命令行参数)
- [配置管理](#配置管理)
- [斜杠命令](#斜杠命令)
- [插件系统](#插件系统)

---

## 架构概览

Hermes CLI 采用模块化架构，主要包含以下部分：

```
hermes_cli/
├── main.py              # 主入口点，命令调度
├── _parser.py           # 参数解析器构建
├── commands.py          # 斜杠命令注册表
├── config.py            # 配置管理
├── auth.py              # 认证管理
├── models.py            # 模型目录
├── gateway.py           # 网关管理
├── status.py            # 状态检查
├── setup.py             # 交互式设置向导
├── plugins.py           # 插件系统
└── ...
```

### 执行流程

1. **初始化阶段** (`main.py`)
   - 应用 profile 覆盖 (`--profile/-p`)
   - 加载环境变量 (`.env`)
   - 初始化日志系统
   - 配置 IPv4 偏好

2. **参数解析** (`_parser.py`)
   - 构建顶层参数解析器
   - 注册子命令
   - 处理继承标志

3. **命令调度** (`main.py`)
   - 根据 `args.command` 分发到对应的 `cmd_*` 函数
   - 执行命令逻辑

---

## 核心组件

### 1. 主入口点 (`main.py`)

负责 CLI 的启动流程和命令分发：

- **Profile 管理**: 支持多 profile 切换，通过 `--profile/-p` 指定
- **环境加载**: 从 `~/.hermes/.env` 和项目根目录 `.env` 加载环境变量
- **日志初始化**: 设置集中式文件日志 (`agent.log`, `errors.log`)
- **命令分发**: 根据参数调用相应的命令处理函数

### 2. 参数解析 (`_parser.py`)

使用 `argparse` 构建命令行参数：

- **顶层参数**: 全局标志如 `--model`, `--provider`, `--skills`
- **子命令**: `chat`, `gateway`, `setup`, `status`, `config` 等
- **继承机制**: 某些标志在重启时自动继承

### 3. 斜杠命令 (`commands.py`)

统一注册所有斜杠命令（如 `/help`, `/new`, `/model`）：

- **COMMAND_REGISTRY**: 中央命令注册表
- **自动补全**: `SlashCommandCompleter` 提供命令和参数补全
- **平台适配**: 为 Telegram、Discord、Slack 等平台生成命令菜单

### 4. 配置管理 (`config.py`)

管理所有配置文件：

- **配置文件**: `~/.hermes/config.yaml`
- **环境文件**: `~/.hermes/.env`
- **缓存机制**: 提高配置读取性能
- **线程安全**: 使用 RLock 保护并发访问

### 5. 认证管理 (`auth.py`)

处理各种 AI 提供商的认证：

- **API 密钥**: OpenAI, Anthropic, OpenRouter 等
- **OAuth**: Microsoft, Google 等提供商
- **凭证池**: 支持多凭证轮换

### 6. 模型目录 (`models.py`)

提供模型列表和验证：

- **内置模型**: 各提供商的推荐模型
- **模型别名**: 简化的模型名称映射
- **动态刷新**: 从 API 获取最新模型列表

### 7. 网关管理 (`gateway.py`)

管理消息网关服务：

- **服务管理**: `start`, `stop`, `restart`, `status`
- **进程监控**: 检测运行中的网关进程
- **服务安装**: systemd (Linux) 和 launchd (macOS)

### 8. 设置向导 (`setup.py`)

交互式配置向导：

- **模型选择**: 选择 AI 提供商和模型
- **终端配置**: 设置命令执行后端
- **平台连接**: 连接 Telegram, Discord 等
- **工具配置**: TTS, 网页搜索等

### 9. 插件系统 (`plugins.py`)

扩展 Hermes 功能：

- **插件源**: Bundled, 用户目录, 项目目录, pip 包
- **生命周期钩子**: 在关键点调用插件回调
- **工具注册**: 插件可注册自定义工具

---

## 命令列表

### 全局命令

| 命令 | 描述 |
|------|------|
| `hermes` | 启动交互式聊天（默认） |
| `hermes chat` | 启动交互式聊天 |
| `hermes -q "prompt"` | 单次查询模式 |
| `hermes -c` | 恢复最近的会话 |
| `hermes -c "name"` | 按名称恢复会话 |
| `hermes --resume <id>` | 按 ID 恢复会话 |
| `hermes setup` | 运行设置向导 |
| `hermes status` | 显示所有组件状态 |
| `hermes doctor` | 诊断配置问题 |
| `hermes version` | 显示版本信息 |
| `hermes update` | 更新到最新版本 |
| `hermes uninstall` | 卸载 Hermes Agent |

### 配置命令

| 命令 | 描述 |
|------|------|
| `hermes config` | 显示当前配置 |
| `hermes config edit` | 在编辑器中打开配置 |
| `hermes config set <key> <value>` | 设置配置值 |
| `hermes logout` | 清除存储的认证信息 |
| `hermes model` | 选择默认模型 |
| `hermes profile` | 显示当前 profile 信息 |

### 认证命令

| 命令 | 描述 |
|------|------|
| `hermes auth add <provider>` | 添加凭证 |
| `hermes auth list` | 列出凭证池 |
| `hermes auth remove <provider>` | 移除凭证 |
| `hermes auth reset <provider>` | 清除提供商的耗尽状态 |

### 网关命令

| 命令 | 描述 |
|------|------|
| `hermes gateway` | 在前台运行网关 |
| `hermes gateway start` | 启动网关服务 |
| `hermes gateway stop` | 停止网关服务 |
| `hermes gateway restart` | 重启网关服务 |
| `hermes gateway status` | 显示网关状态 |
| `hermes gateway install` | 安装网关服务 |
| `hermes gateway uninstall` | 卸载网关服务 |

### 会话管理命令

| 命令 | 描述 |
|------|------|
| `hermes sessions list` | 列出历史会话 |
| `hermes sessions browse` | 交互式会话选择器 |
| `hermes sessions rename <id> <title>` | 重命名会话 |

### 日志命令

| 命令 | 描述 |
|------|------|
| `hermes logs` | 查看 agent.log（最后 50 行） |
| `hermes logs -f` | 实时跟踪 agent.log |
| `hermes logs errors` | 查看 errors.log |
| `hermes logs --since 1h` | 查看最近 1 小时的日志 |

### Cron 命令

| 命令 | 描述 |
|------|------|
| `hermes cron` | 管理 cron 任务 |
| `hermes cron list` | 列出 cron 任务 |
| `hermes cron status` | 检查 cron 调度器状态 |

---

## 使用示例

### 基础使用

```bash
# 启动交互式聊天
hermes

# 单次查询
hermes -q "解释一下 Docker 的基本概念"

# 使用特定模型
hermes -m anthropic/claude-sonnet-4.6 -q "写一个 Python 脚本"

# 恢复最近的会话
hermes -c

# 按名称恢复会话
hermes -c "my-project"

# 预加载 skills
hermes -s tdd-workflow,simplify
```

### 配置管理

```bash
# 查看配置
hermes config

# 编辑配置
hermes config edit

# 设置模型
hermes config set model anthropic/claude-sonnet-4.6

# 选择模型
hermes model
```

### 认证管理

```bash
# 添加 OpenAI 凭证
hermes auth add openai

# 列出凭证池
hermes auth list

# 移除凭证
hermes auth remove openai 0

# 重置提供商状态
hermes auth reset openrouter
```

### 网关管理

```bash
# 在前台运行网关
hermes gateway

# 启动网关服务
hermes gateway start

# 检查网关状态
hermes gateway status

# 停止网关服务
hermes gateway stop
```

### 调试

```bash
# 查看状态
hermes status

# 诊断问题
hermes doctor

# 查看日志
hermes logs -f

# 上传调试报告
hermes debug share
```

---

## 命令行参数

### 全局参数

| 参数 | 简写 | 描述 |
|------|------|------|
| `--version` | `-V` | 显示版本并退出 |
| `--oneshot PROMPT` | `-z` | 单次模式：发送提示并仅输出响应 |
| `--model MODEL` | `-m` | 覆盖本次调用的模型 |
| `--provider PROVIDER` | | 覆盖本次调用的提供商 |
| `--toolsets LIST` | `-t` | 启用的工具集（逗号分隔） |
| `--resume SESSION` | `-r` | 按 ID 恢复会话 |
| `--continue [NAME]` | `-c` | 恢复最近或指定名称的会话 |
| `--worktree` | `-w` | 在隔离的 git worktree 中运行 |
| `--accept-hooks` | | 自动批准 shell hooks |
| `--skills LIST` | `-s` | 预加载 skills（可重复或逗号分隔） |
| `--yolo` | | 跳过所有危险命令批准提示 |
| `--pass-session-id` | | 在系统提示中包含会话 ID |
| `--ignore-user-config` | | 忽略用户配置文件 |
| `--ignore-rules` | | 跳过 AGENTS.md, SOUL.md 等规则注入 |
| `--tui` | | 启动现代 TUI 而非经典 REPL |
| `--dev` | | 与 --tui 配合：运行 TypeScript 源码 |
| `--profile NAME` | `-p` | 使用指定的 profile |

### Chat 命令参数

| 参数 | 简写 | 描述 |
|------|------|------|
| `--query PROMPT` | `-q` | 单次查询（非交互模式） |
| `--image PATH` | | 附加本地图片到单次查询 |
| `--verbose` | `-v` | 详细输出 |
| `--quiet` | `-Q` | 静默模式（程序化使用） |
| `--checkpoints` | | 在破坏性文件操作前启用文件系统检查点 |
| `--max-turns N` | | 每轮对话的最大工具调用迭代次数 |
| `--source TAG` | | 会话来源标签（默认：cli） |

---

## 配置管理

### 配置文件位置

- **配置文件**: `~/.hermes/config.yaml`
- **环境文件**: `~/.hermes/.env`
- **Profile 目录**: `~/.hermes/profiles/<name>/`

### 主要配置项

```yaml
# 模型配置
model:
  default: "anthropic/claude-sonnet-4.6"

# 提供商配置
providers:
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"

# 工具集配置
toolsets:
  - "default"

# 终端配置
terminal:
  backend: "auto"  # auto, pty, ssh, container

# 会话配置
session:
  max_turns: 90
  auto_compress: true

# 显示配置
display:
  tool_progress: "new"  # off, new, all, verbose

# Hook 配置
hooks:
  auto_accept: false

# 网络配置
network:
  force_ipv4: false
```

### 环境变量

常用环境变量（在 `.env` 中设置）：

```bash
# API 密钥
OPENROUTER_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here

# Hermes 配置
HERMES_HOME=/path/to/hermes/home
HERMES_ACCEPT_HOOKS=1
HERMES_REDACT_SECRETS=true

# 网关配置
TELEGRAM_BOT_TOKEN=your_token_here
DISCORD_BOT_TOKEN=your_token_here
```

---

## 斜杠命令

斜杠命令在聊天会话中提供快捷操作，例如 `/help`, `/new`, `/model`。

### 命令分类

#### 会话管理

| 命令 | 别名 | 描述 |
|------|------|------|
| `/new` | `/reset` | 开始新会话 |
| `/clear` | | 清屏并开始新会话 |
| `/redraw` | | 强制 UI 重绘 |
| `/history` | | 显示对话历史 |
| `/save` | | 保存当前对话 |
| `/retry` | | 重发最后一条消息 |
| `/undo` | | 撤销最后一次交换 |
| `/title [name]` | | 设置会话标题 |
| `/branch [name]` | `/fork` | 分支当前会话 |
| `/compress [topic]` | | 手动压缩对话上下文 |
| `/rollback [n]` | | 列出或恢复文件系统检查点 |
| `/snapshot` | `/snap` | 创建或恢复状态快照 |
| `/stop` | | 停止所有后台进程 |
| `/status` | | 显示会话信息 |

#### 后台执行

| 命令 | 别名 | 描述 |
|------|------|------|
| `/background <prompt>` | `/bg`, `/btw` | 在后台运行提示 |
| `/agents` | `/tasks` | 显示活跃的代理和运行的任务 |
| `/queue <prompt>` | `/q` | 将提示排队到下一轮 |
| `/steer <prompt>` | | 在下一次工具调用后注入消息 |
| `/goal [text|pause|resume|clear|status]` | | 设置目标 |
| `/subgoal [text|remove|clear]` | | 管理额外目标 |

#### 配置

| 命令 | 别名 | 描述 |
|------|------|------|
| `/config` | | 显示当前配置 |
| `/model [model]` | `/provider` | 切换当前会话的模型 |
| `/personality [name]` | | 设置预定义个性 |
| `/verbose` | | 循环工具进度显示 |
| `/yolo` | | 切换 YOLO 模式（跳过批准） |
| `/reasoning [level|show|hide]` | | 管理推理强度和显示 |
| `/fast [normal|fast|status]` | | 切换快速模式 |
| `/skin [name]` | | 显示或更改显示皮肤/主题 |

#### 工具与 Skills

| 命令 | 描述 |
|------|------|
| `/tools [list|disable|enable]` | 管理工具 |
| `/toolsets` | 列出可用工具集 |
| `/skills [search|browse|install]` | 搜索、安装、管理 skills |
| `/bundles` | 列出 skill bundles |
| `/cron [list|add|create|edit...]` | 管理定时任务 |
| `/curator [status|run|pin...]` | 后台 skill 维护 |
| `/kanban [init|boards|create...]` | 多 profile 协作看板 |
| `/reload` | 重新加载 .env 变量 |
| `/reload-mcp` | 重新加载 MCP 服务器 |
| `/reload-skills` | 重新扫描 skills 目录 |
| `/browser [connect|disconnect|status]` | 连接浏览器工具 |
| `/plugins` | 列出已安装的插件 |

#### 信息

| 命令 | 描述 |
|------|------|
| `/help` | 显示可用命令 |
| `/whoami` | 显示斜杠命令访问权限 |
| `/profile` | 显示活动 profile 名称 |
| `/usage` | 显示当前会话的令牌使用情况 |
| `/insights [days]` | 显示使用洞察和分析 |
| `/platforms` | 显示网关/消息平台状态 |
| `/copy [n]` | 将最后一次助手响应复制到剪贴板 |
| `/paste` | 从剪贴板附加图片 |
| `/image <path>` | 附加本地图片 |
| `/update` | 更新到最新版本 |
| `/debug` | 上传调试报告 |

#### 退出

| 命令 | 别名 | 描述 |
|------|------|------|
| `/quit [--delete]` | `/exit` | 退出 CLI（使用 --delete 同时删除会话历史） |

### 自动补全

CLI 支持命令和参数的智能自动补全：

- **命令补全**: 输入 `/hel` → 补全为 `/help`
- **子命令补全**: 输入 `/model c` → 显示 `claude-*` 系列模型
- **路径补全**: 输入 `./src/` → 补全文件路径
- **上下文引用**: 输入 `@` → 补全项目文件和特殊引用

---

## 插件系统

Hermes 插件系统提供四种插件源：

1. **Bundled 插件**: `<repo>/plugins/<name>/`
2. **用户插件**: `~/.hermes/plugins/<name>/`
3. **项目插件**: `./.hermes/plugins/<name>/`
4. **Pip 插件**: 通过 `hermes_agent.plugins` entry point 安装

### 插件结构

每个目录插件必须包含：

```
<plugin-name>/
├── plugin.yaml      # 插件清单
└── __init__.py      # 注册函数
```

### 插件清单 (`plugin.yaml`)

```yaml
name: "my-plugin"
version: "1.0.0"
description: "My custom plugin"
author: "Your Name"
hermes_version: ">=0.14.0"
```

### 注册函数 (`__init__.py`)

```python
from hermes_cli.plugins import PluginContext

def register(ctx: PluginContext):
    # 注册钩子
    ctx.register_hook("before_tool_call", my_hook)

    # 注册工具
    ctx.register_tool(my_tool)

    # 注册斜杠命令
    ctx.register_command("mycmd", "My command")
```

### 生命周期钩子

可用钩子（`VALID_HOOKS`）：

- `before_tool_call`: 工具调用前
- `after_tool_call`: 工具调用后
- `before_agent_turn`: 代理轮次前
- `after_agent_turn`: 代理轮次后
- `on_user_message`: 用户消息时
- `on_assistant_message`: 助手消息时

---

## 高级特性

### Profile 系统

支持多 profile 配置，实现不同环境隔离：

```bash
# 切换 profile
hermes -p dev

# 设置默认 profile
hermes profile use dev

# 列出 profiles
hermes profile list
```

### Worktree 模式

在隔离的 git worktree 中运行，支持并行代理：

```bash
hermes -w
```

### One-shot 模式

脚本友好的单次模式：

```bash
# 仅输出最终响应，无额外输出
hermes -z "解释 Python 装饰器"
```

### TUI 模式

现代终端界面：

```bash
hermes --tui
```

### 检查点系统

在破坏性操作前创建文件系统检查点：

```bash
hermes chat --checkpoints
# 使用 /rollback 恢复
```

---

## 调试与故障排除

### 查看日志

```bash
# 实时跟踪日志
hermes logs -f

# 查看错误日志
hermes logs errors

# 查看最近 1 小时的日志
hermes logs --since 1h
```

### 诊断工具

```bash
# 运行诊断
hermes doctor

# 查看状态
hermes status

# 上传调试报告
hermes debug share
```

### 调试模式

设置环境变量启用调试：

```bash
HERMES_PLUGINS_DEBUG=1 hermes
```

---

## 相关文档

- [Gateway 文档](../gateway/README.md)
- [Agent 核心文档](../agent/README.md)
- [插件开发指南](../plugins/README.md)
- [主项目 README](../README.md)

---

## 版本信息

当前版本: `0.14.0` (2026.05.16)