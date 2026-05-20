# Hermes Agent 配置文档

本指南详细介绍 Hermes Agent 的所有配置选项，包括 config.yaml 配置文件和环境变量。

## 目录

- [配置文件位置](#配置文件位置)
- [配置文件结构](#配置文件结构)
- [模型配置](#模型配置)
- [终端配置](#终端配置)
- [浏览器配置](#浏览器配置)
- [工具循环保护](#工具循环保护)
- [上下文压缩](#上下文压缩)
- [持久化记忆](#持久化记忆)
- [会话重置策略](#会话重置策略)
- [技能配置](#技能配置)
- [代理行为配置](#代理行为配置)
- [工具集配置](#工具集配置)
- [MCP 服务器配置](#mcp-服务器配置)
- [语音转文字配置](#语音转文字配置)
- [显示配置](#显示配置)
- [环境变量](#环境变量)
- [配置示例](#配置示例)

## 配置文件位置

Hermes Agent 使用以下配置文件：

```
~/.hermes/
├── config.yaml          # 主配置文件
├── .env                 # 环境变量（敏感信息）
├── skills/              # 技能目录
├── logs/                # 日志目录
└── skins/               # 主题目录（可选）
```

### 创建配置文件

首次运行时，可以从示例文件复制：

```bash
# 创建配置目录
mkdir -p ~/.hermes

# 复制示例配置文件
cp cli-config.yaml.example ~/.hermes/config.yaml
cp .env.example ~/.hermes/.env

# 编辑配置
nano ~/.hermes/config.yaml
nano ~/.hermes/.env
```

### 配置命令

```bash
# 查看当前配置
hermes config list

# 设置配置项
hermes config set model.default anthropic/claude-opus-4.6
hermes config set terminal.backend docker

# 获取配置项
hermes config get model.default

# 编辑配置文件（使用默认编辑器）
hermes config edit
```

## 配置文件结构

config.yaml 使用 YAML 格式，包含以下主要部分：

```yaml
# 模型配置
model:
  default: "anthropic/claude-opus-4.6"
  provider: "auto"
  base_url: "https://openrouter.ai/api/v1"

# 终端配置
terminal:
  backend: "local"
  cwd: "."
  timeout: 180

# 其他配置...
```

## 模型配置

### 基础配置

```yaml
model:
  # 默认模型（必需）
  # 支持的模型：anthropic/claude-opus-4.6, anthropic/claude-sonnet-4.6,
  #            google/gemini-3-flash-preview, openai/gpt-4o, 等
  default: "anthropic/claude-opus-4.6"
  
  # 提供商选择（可选，默认 auto）
  # auto - 自动检测
  # openrouter - OpenRouter
  # nous - Nous Portal OAuth
  # anthropic - 原生 Anthropic
  # openai-codex - OpenAI Codex
  # gemini - Google AI Studio
  # zai - z.ai / GLM
  # kimi-coding - Kimi / Moonshot
  # minimax - MiniMax
  # huggingface - Hugging Face
  # custom - 自定义端点
  provider: "auto"
  
  # API 基础 URL（可选）
  base_url: "https://openrouter.ai/api/v1"
  
  # API 密钥（可选，推荐在 .env 中设置）
  # api_key: "your-api-key-here"
  
  # 上下文长度（可选，通常自动检测）
  # context_length: 131072
  
  # 最大输出 token 数（可选）
  # max_tokens: 8192
```

### 提供商特定配置

```yaml
model:
  # OpenRouter 提供商路由
  provider_routing:
    # 排序策略：price, throughput, latency
    sort: "throughput"
    
    # 仅允许的提供商
    # only: ["anthropic", "google"]
    
    # 跳过的提供商
    # ignore: ["deepinfra", "fireworks"]
    
    # 尝试顺序
    # order: ["anthropic", "google", "together"]
    
    # 要求提供商支持所有参数
    # require_parameters: true
    
    # 数据政策：allow 或 deny
    # data_collection: "deny"
  
  # OpenRouter 响应缓存
  openrouter:
    response_cache: true
    response_cache_ttl: 300  # 秒
  
  # 每个提供商的超时配置
  providers:
    ollama-local:
      request_timeout_seconds: 300
      stale_timeout_seconds: 900
    anthropic:
      request_timeout_seconds: 30
      models:
        claude-opus-4.6:
          timeout_seconds: 600
```

### Azure Foundry 配置

```yaml
model:
  provider: "azure-foundry"
  base_url: "https://your-resource.openai.azure.com/openai/v1"
  auth_mode: "entra_id"  # 或 "api_key"
  default: "gpt-4o"
  
  # Entra ID 配置（可选）
  entra:
    scope: "https://ai.azure.com/.default"
```

### 自定义端点配置

```yaml
model:
  provider: "custom"
  base_url: "http://localhost:11434/v1"
  default: "llama2"
```

## 终端配置

终端工具支持多种后端，提供不同级别的隔离。

### 本地执行（默认）

```yaml
terminal:
  backend: "local"
  cwd: "."  # 当前工作目录
  timeout: 180  # 命令超时（秒）
  lifetime_seconds: 300  # 环境生命周期
  
  # sudo 密码（可选，安全警告：明文存储）
  # sudo_password: "your-password"
```

### SSH 远程执行

```yaml
terminal:
  backend: "ssh"
  cwd: "/home/user/project"  # 远程服务器上的路径
  timeout: 180
  lifetime_seconds: 300
  ssh_host: "server.example.com"
  ssh_user: "your-username"
  ssh_port: 22
  ssh_key: "~/.ssh/id_rsa"  # 可选，默认使用 ssh-agent
```

### Docker 容器

```yaml
terminal:
  backend: "docker"
  cwd: "/workspace"  # 容器内路径
  timeout: 180
  lifetime_seconds: 300
  docker_image: "nikolaik/python-nodejs:python3.11-nodejs20"
  
  # 安全：是否挂载当前目录到容器
  docker_mount_cwd_to_workspace: false  # 默认为 false，推荐保持
  
  # 使用宿主机用户 UID/GID 运行
  docker_run_as_host_user: true
  
  # 传递环境变量到容器
  docker_forward_env:
    - "GITHUB_TOKEN"
    - "NPM_TOKEN"
  
  # 额外的 docker run 参数
  docker_extra_args:
    - "--cap-add"
    - "SETUID"
  
  # 容器资源限制
  container_cpu: 2.0
  container_memory: 4096  # MB
  container_disk: 51200  # MB
  container_persistent: true  # 是否持久化文件系统
```

### Singularity 容器

```yaml
terminal:
  backend: "singularity"
  cwd: "/workspace"
  timeout: 180
  lifetime_seconds: 300
  singularity_image: "docker://nikolaik/python-nodejs:python3.11-nodejs20"
  container_cpu: 2.0
  container_memory: 4096
```

### Modal 云执行

```yaml
terminal:
  backend: "modal"
  cwd: "/workspace"
  timeout: 180
  lifetime_seconds: 300
  modal_image: "nikolaik/python-nodejs:python3.11-nodejs20"
  container_cpu: 2.0
  container_memory: 4096
```

### Daytona 云执行

```yaml
terminal:
  backend: "daytona"
  cwd: "~"
  timeout: 180
  lifetime_seconds: 300
  daytona_image: "nikolaik/python-nodejs:python3.11-nodejs20"
  container_disk: 10240  # MB
```

## 浏览器配置

浏览器自动化工具的配置。

```yaml
browser:
  # 不活动超时（秒）
  inactivity_timeout: 120
  
  # 浏览器引擎
  # auto - 自动选择
  # chrome - Chrome
  # lightpanda - Lightpanda（更快，但不支持截图）
  engine: "auto"
```

## 工具循环保护

防止代理陷入无限工具调用循环。

```yaml
tool_loop_guardrails:
  # 启用软警告
  warnings_enabled: true
  
  # 启用硬停止
  hard_stop_enabled: false
  
  # 警告阈值
  warn_after:
    exact_failure: 2  # 相同失败次数
    same_tool_failure: 3  # 相同工具失败次数
    idempotent_no_progress: 2  # 无进展次数
  
  # 硬停止阈值
  hard_stop_after:
    exact_failure: 5
    same_tool_failure: 8
    idempotent_no_progress: 5
```

## 上下文压缩

当对话接近模型上下文限制时，自动压缩中间对话。

```yaml
compression:
  # 启用自动压缩
  enabled: true
  
  # 触发压缩的阈值（上下文限制的百分比）
  threshold: 0.50  # 50%
  
  # 保留的最近上下文比例
  target_ratio: 0.20  # 20%
  
  # 保护的最近消息数
  protect_last_n: 20
  
  # 保护的头部非系统消息数
  protect_first_n: 3
```

## 提示缓存

Anthropic 提示缓存配置。

```yaml
prompt_caching:
  # 缓存 TTL："5m" 或 "1h"
  cache_ttl: "5m"
```

## 辅助模型

用于图像分析、网页摘要、上下文压缩等辅助任务的模型。

```yaml
auxiliary:
  # 图像分析
  vision:
    provider: "auto"
    model: ""
    timeout: 30
    download_timeout: 30
  
  # 网页提取和摘要
  web_extract:
    provider: "auto"
    model: ""
  
  # 会话搜索
  session_search:
    provider: "auto"
    model: ""
    timeout: 30
    max_concurrency: 3
    extra_body: {}
```

## 持久化记忆

跨会话持久化的记忆系统。

```yaml
memory:
  # 启用代理记忆（MEMORY.md）
  memory_enabled: true
  
  # 启用户画像（USER.md）
  user_profile_enabled: true
  
  # 字符限制
  memory_char_limit: 2200  # ~800 tokens
  user_char_limit: 1375  # ~500 tokens
  
  # 定期提醒间隔（用户对话次数）
  nudge_interval: 10
  
  # 记忆刷新：在上下文丢失前保存
  flush_min_turns: 6  # 触发刷新的最少用户对话数
```

## 会话重置策略

消息平台上的会话自动重置策略。

```yaml
session_reset:
  # 重置模式：both, idle, daily, none
  mode: "both"
  
  # 不活动超时（分钟）
  idle_minutes: 1440  # 24 小时
  
  # 每日重置时间（小时，本地时间）
  at_hour: 4  # 凌晨 4 点

# 群组/频道中每个用户单独会话
group_sessions_per_user: true
```

## 网关流式传输

在消息平台上实时流式传输 token。

```yaml
streaming:
  enabled: false
  
  # 传输方式：edit
  transport: "edit"
  
  # 编辑间隔（秒）
  edit_interval: 0.3
  
  # 缓冲区阈值（字符）
  buffer_threshold: 40
  
  # 光标
  cursor: " ▉"
```

## 技能配置

技能系统配置。

```yaml
skills:
  # 创建技能提醒间隔（工具调用迭代次数）
  creation_nudge_interval: 15
  
  # 外部技能目录
  external_dirs:
    - "~/.agents/skills"
    - "/home/shared/team-skills"
```

## 代理行为配置

代理的一般行为配置。

```yaml
agent:
  # 最大工具调用迭代次数
  max_turns: 60
  
  # 网关不活动超时（秒，0 = 无限制）
  gateway_timeout: 1800  # 30 分钟
  
  # 超时警告阈值（秒）
  gateway_timeout_warning: 900  # 15 分钟
  
  # 优雅关闭等待时间（秒）
  restart_drain_timeout: 60
  
  # API 最大重试次数
  api_max_retries: 3
  
  # 详细日志
  verbose: false
  
  # 推理努力级别：xhigh, high, medium, low, minimal, none
  reasoning_effort: "medium"
  
  # 预定义人格
  personalities:
    helpful: "You are a helpful, friendly AI assistant."
    concise: "You are a concise assistant. Keep responses brief and to the point."
    technical: "You are a technical expert. Provide detailed, accurate technical information."
    creative: "You are a creative assistant. Think outside the box and offer innovative solutions."
    teacher: "You are a patient teacher. Explain concepts clearly with examples."
    kawaii: "You are a kawaii assistant! Use cute expressions like (◕‿◕), ★, ♪, and ~!"
    catgirl: "You are Neko-chan, an anime catgirl AI assistant, nya~!"
    pirate: "Arrr! Ye be talkin' to Captain Hermes, the most tech-savvy pirate!"
    # 添加更多自定义人格...
```

## 工具集配置

配置每个平台可用的工具。

### 平台工具集预设

```yaml
platform_toolsets:
  # CLI 工具集
  cli: ["hermes-cli"]
  
  # 消息平台工具集
  telegram: ["hermes-telegram"]
  discord: ["hermes-discord"]
  whatsapp: ["hermes-whatsapp"]
  slack: ["hermes-slack"]
  teams: ["hermes-teams"]
  google_chat: ["hermes-google_chat"]
```

### 自定义工具集

```yaml
# 自定义工具集（示例）
platform_toolsets:
  # 限制 Telegram 只能使用安全工具
  telegram: ["web", "vision", "skills", "todo"]
  
  # 给 CLI 更多工具权限
  cli: ["web", "terminal", "file", "browser", "vision", "skills", "todo", "tts", "cronjob"]
```

### 可用工具集

单个工具集：
- `web` - Web 搜索和内容提取
- `search` - 仅 Web 搜索
- `terminal` - 终端访问
- `file` - 文件操作
- `browser` - 浏览器自动化
- `vision` - 图像分析
- `image_gen` - 图像生成
- `skills` - 技能系统
- `skills_hub` - 技能中心
- `moa` - 混合代理
- `todo` - 任务规划
- `tts` - 文本转语音
- `cronjob` - 定时任务

复合工具集：
- `hermes-cli` - 完整 CLI 工具集
- `hermes-telegram` - Telegram 工具集
- `hermes-discord` - Discord 工具集
- `debugging` - 调试工具集
- `safe` - 安全工具集（无终端访问）
- `all` - 所有可用工具集

## MCP 服务器配置

连接外部 MCP（Model Context Protocol）服务器。

```yaml
mcp_servers:
  # 时间服务器示例
  time:
    command: "uvx"
    args: ["mcp-server-time"]
  
  # 文件系统服务器示例
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/home/user"]
  
  # Notion 服务器示例
  notion:
    url: "https://mcp.notion.com/mcp"
  
  # GitHub 服务器示例
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "ghp_xxx"
  
  # 自定义服务器示例
  custom:
    command: "python"
    args: ["-m", "custom_mcp_server"]
    timeout: 120
    connect_timeout: 60
```

### MCP 采样配置

```yaml
mcp_servers:
  analysis:
    command: "npx"
    args: ["-y", "analysis-server"]
    sampling:
      enabled: true
      model: "gemini-3-flash"
      max_tokens_cap: 4096
      timeout: 30
      max_rpm: 10
      allowed_models: []
      max_tool_rounds: 5
      log_level: "info"
```

## 语音转文字配置

语音消息自动转录配置。

```yaml
stt:
  # 启用语音转录
  enabled: true
  
  # 提供商（可选，自动检测）
  # local - 本地 faster-whisper
  # groq - Groq Whisper API
  # openai - OpenAI Whisper API
  provider: "local"
  
  # 本地提供者配置
  local:
    model: "base"  # tiny, base, small, medium, large-v3, turbo
    language: ""  # 留空自动检测，或设置为 "en", "zh", 等
  
  # OpenAI 提供者配置
  openai:
    model: "whisper-1"  # whisper-1, gpt-4o-mini-transcribe, gpt-4o-transcribe
  
  # Groq 提供者配置
  groq:
    model: "whisper-large-v3-turbo"
```

## 响应节奏配置

在消息平台上添加人类风格的延迟。

```yaml
human_delay:
  # 模式：off, natural, custom
  mode: "off"
  
  # 自定义模式下的最小/最大延迟（毫秒）
  min_ms: 800
  max_ms: 2500
```

## 代码执行沙箱配置

代码执行工具配置。

```yaml
code_execution:
  # 超时时间（秒）
  timeout: 300  # 5 分钟
  
  # 最大工具调用次数
  max_tool_calls: 50
```

## 子代理委托配置

子代理工具配置。

```yaml
delegation:
  # 子代理最大迭代次数
  max_iterations: 50
  
  # 最大并发子代理数
  max_concurrent_children: 3
  
  # 最大委托深度
  max_spawn_depth: 1
  
  # 启用编排器角色
  orchestrator_enabled: true
  
  # 子代理自动批准
  subagent_auto_approve: false  # true = 自动批准，false = 阻止
  
  # 继承 MCP 工具集
  inherit_mcp_toolsets: true
  
  # 子代理模型覆盖（可选）
  model: ""
  provider: ""
```

## Honcho 集成配置

跨会话用户建模集成。

```yaml
honcho:
  # 大多数配置来自 ~/.honcho/config.json
  # 这里可以覆盖特定配置
  enabled: true
```

## 显示配置

UI 显示配置。

```yaml
display:
  # 紧凑横幅模式
  compact: false
  
  # 工具进度显示级别：off, new, all, verbose
  tool_progress: "all"
  
  # 清理进度气泡
  cleanup_progress: false
  
  # 平台特定显示配置
  platforms:
    telegram:
      cleanup_progress: true
  
  # 中间助手消息
  interim_assistant_messages: true
  
  # 忙碌输入模式：interrupt, queue, steer
  busy_input_mode: "interrupt"
  
  # 后台进程通知级别：off, result, error, all
  background_process_notifications: "all"
  
  # 完成时响铃
  bell_on_complete: false
  
  # 显示推推理过程
  show_reasoning: false
  
  # 流式传输 token
  streaming: true
  
  # 显示时间戳
  timestamps: false
  
  # 主题/皮肤：default, ares, mono, slate, daylight, warm-lightmode, poseidon, sisyphus, charizard
  skin: "default"
```

## 模型别名

为 `/model` 命令创建简短别名。

```yaml
model_aliases:
  opus:
    model: "claude-opus-4.6"
    provider: "anthropic"
  
  sonnet:
    model: "claude-sonnet-4.6"
    provider: "anthropic"
  
  gemini:
    model: "gemini-3-flash-preview"
    provider: "gemini"
  
  # 本地模型别名
  local-llama:
    model: "llama2"
    provider: "custom"
    base_url: "http://localhost:11434/v1"
```

## 隐私配置

```yaml
privacy:
  # 从 LLM 上下文中删除 PII（个人身份信息）
  redact_pii: false
```

## 安全扫描配置

可选的预执行命令安全扫描。

```yaml
security:
  # 启用 tirith 安全扫描
  tirith_enabled: false
  
  # tirith 路径
  tirith_path: "tirith"
  
  # 扫描超时
  tirith_timeout: 5
  
  # 失败时打开（允许命令继续）
  tirith_fail_open: true
```

## 平台配置

特定消息平台的配置。

```yaml
platforms:
  telegram:
    # 回复模式：off, first, all
    reply_to_mode: "first"
    
    # 访客模式：允许来自非允许列表群组的提及
    guest_mode: false
    
    # 允许的聊天 ID 列表
    # allowed_chats: ["-1001234567890"]
    
    # 额外配置
    extra:
      # 禁用链接预览
      disable_link_previews: false

# Discord 特定配置（顶层键）
discord:
  # 要求提及才能响应
  require_mention: true
  
  # 自动创建线程
  auto_thread: true
  
  # 自由响应频道（不需要提及）
  free_response_channels: ""
  
  # 显示反应
  reactions: true
  
  # 历史回溯
  history_backfill: true
  history_backfill_limit: 50
```

## 环境变量

除了 config.yaml 外，还可以使用环境变量配置，这些变量通常存储在 `~/.hermes/.env` 文件中。

### LLM 提供商密钥

```bash
# OpenRouter（推荐）
OPENROUTER_API_KEY=sk-or-v1-xxx

# Anthropic 原生
ANTHROPIC_API_KEY=sk-ant-xxx

# Google AI Studio / Gemini
GOOGLE_API_KEY=xxx
GEMINI_API_KEY=xxx  # GOOGLE_API_KEY 的别名

# OpenAI
OPENAI_API_KEY=sk-xxx

# z.ai / GLM
GLM_API_KEY=xxx
GLM_BASE_URL=https://api.z.ai/api/paas/v4

# Kimi / Moonshot
KIMI_API_KEY=xxx
KIMI_BASE_URL=https://api.kimi.com/coding/v1

# MiniMax
MINIMAX_API_KEY=xxx
MINIMAX_BASE_URL=https://api.minimax.io/v1

# Hugging Face
HF_TOKEN=xxx

# Ollama Cloud
OLLAMA_API_KEY=xxx
OLLAMA_BASE_URL=https://ollama.com/v1
```

### 工具密钥

```bash
# Exa Web 搜索
EXA_API_KEY=xxx

# Parallel Web 搜索
PARALLEL_API_KEY=xxx

# Firecrawl Web 搜索/爬虫
FIRECRAWL_API_KEY=xxx

# FAL 图像生成
FAL_KEY=xxx

# Browserbase 浏览器自动化
BROWSERBASE_API_KEY=xxx
BROWSERBASE_PROJECT_ID=xxx
BROWSERBASE_PROXIES=true
BROWSERBASE_ADVANCED_STEALTH=false

# 代理浏览器引擎
AGENT_BROWSER_ENGINE=auto
AGENT_BROWSER_ARGS=--no-sandbox

# Camofox 反检测浏览器
CAMOFOX_URL=http://localhost:9377
CAMOFOX_USER_ID=xxx
CAMOFOX_SESSION_KEY=xxx
CAMOFOX_ADOPT_EXISTING_TAB=false
```

### 终端配置

```bash
# 终端后端覆盖
TERMINAL_ENV=local

# Docker 二进制路径覆盖
HERMES_DOCKER_BINARY=/usr/local/bin/podman

# 终端图像
TERMINAL_DOCKER_IMAGE=nikolaik/python-nodejs:python3.11-nodejs20
TERMINAL_SINGULARITY_IMAGE=docker://nikolaik/python-nodejs:python3.11-nodejs20
TERMINAL_MODAL_IMAGE=nikolaik/python-nodejs:python3.11-nodejs20

# 终端工作目录
TERMINAL_CWD=.

# 超时设置
TERMINAL_TIMEOUT=180
TERMINAL_LIFETIME_SECONDS=300

# SSH 配置
TERMINAL_SSH_HOST=server.example.com
TERMINAL_SSH_USER=user
TERMINAL_SSH_PORT=22
TERMINAL_SSH_KEY=~/.ssh/id_rsa

# Sudo 密码（安全警告：明文存储）
SUDO_PASSWORD=xxx
```

### 语音工具

```bash
# OpenAI 语音工具（用于 Whisper 和 TTS）
VOICE_TOOLS_OPENAI_KEY=sk-xxx

# Groq 语音工具（免费 Whisper）
GROQ_API_KEY=xxx
```

### 消息平台密钥

```bash
# Slack
SLACK_BOT_TOKEN=xoxb-xxx
SLACK_APP_TOKEN=xapp-1-xxx
SLACK_ALLOWED_USERS=U123,U456

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_ALLOWED_USERS=123456,789012
TELEGRAM_HOME_CHANNEL=-1001234567890
TELEGRAM_HOME_CHANNEL_NAME=My Hermes Channel
TELEGRAM_CRON_THREAD_ID=456

# Telegram Webhook
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram
TELEGRAM_WEBHOOK_PORT=8443
TELEGRAM_WEBHOOK_SECRET=xxx

# WhatsApp
WHATSAPP_ENABLED=false
WHATSAPP_ALLOWED_USERS=15551234567

# Email
EMAIL_ADDRESS=hermes@gmail.com
EMAIL_PASSWORD=xxx
EMAIL_IMAP_HOST=imap.gmail.com
EMAIL_IMAP_PORT=993
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_POLL_INTERVAL=15
EMAIL_ALLOWED_USERS=your@email.com
EMAIL_HOME_ADDRESS=your@email.com

# Microsoft Teams
TEAMS_CLIENT_ID=xxx
TEAMS_CLIENT_SECRET=xxx
TEAMS_TENANT_ID=common
TEAMS_ALLOWED_USERS=xxx
TEAMS_ALLOW_ALL_USERS=false
TEAMS_HOME_CHANNEL=xxx
TEAMS_HOME_CHANNEL_NAME=xxx
TEAMS_PORT=3978

# Google Chat
GOOGLE_CHAT_PROJECT_ID=xxx
GOOGLE_CHAT_SUBSCRIPTION_NAME=projects/xxx/subscriptions/xxx
GOOGLE_CHAT_SERVICE_ACCOUNT_JSON=/path/to/sa.json
GOOGLE_CHAT_ALLOWED_USERS=user@example.com
GOOGLE_CHAT_ALLOW_ALL_USERS=false
GOOGLE_CHAT_HOME_CHANNEL=spaces/xxx
GOOGLE_CHAT_HOME_CHANNEL_NAME=xxx
```

### 网关通用配置

```bash
# 允许所有用户（安全警告：仅在受信任环境中使用）
GATEWAY_ALLOW_ALL_USERS=false
```

### 响应节奏

```bash
# 人类延迟模式
HERMES_HUMAN_DELAY_MODE=off  # off, natural, custom
HERMES_HUMAN_DELAY_MIN_MS=800
HERMES_HUMAN_DELAY_MAX_MS=2500
```

### 调试选项

```bash
# 调试模式
WEB_TOOLS_DEBUG=false
VISION_TOOLS_DEBUG=false
MOA_TOOLS_DEBUG=false
IMAGE_TOOLS_DEBUG=false
```

### 上下文压缩（已弃用，使用 config.yaml）

```bash
# 这些是旧的配置方式，推荐使用 config.yaml
CONTEXT_COMPRESSION_ENABLED=true
CONTEXT_COMPRESSION_THRESHOLD=0.85
```

### Skill Hub

```bash
# GitHub Token（用于更高的 API 速率限制）
GITHUB_TOKEN=ghp_xxx

# GitHub App（用于 PR 的机器人身份）
GITHUB_APP_ID=xxx
GITHUB_APP_PRIVATE_KEY_PATH=/path/to/key.pem
GITHUB_APP_INSTALLATION_ID=xxx
```

### STT 覆盖

```bash
# STT 模型覆盖
STT_GROQ_MODEL=whisper-large-v3-turbo
STT_OPENAI_MODEL=whisper-1

# STT 端点覆盖
GROQ_BASE_URL=https://api.groq.com/openai/v1
STT_OPENAI_BASE_URL=https://api.openai.com/v1
```

### API 服务器

```bash
# OpenAI 兼容 API 服务器
API_SERVER_HOST=127.0.0.1
API_SERVER_KEY=xxx  # 必需的认证密钥
```

### 钩子自动接受

```bash
# 自动接受钩子（用于非交互式环境）
HERMES_ACCEPT_HOOKS=1
```

## 配置示例

### 最小配置示例

```yaml
# ~/.hermes/config.yaml
model:
  default: "anthropic/claude-opus-4.6"
  provider: "openrouter"

terminal:
  backend: "local"

platform_toolsets:
  cli: ["hermes-cli"]
  telegram: ["hermes-telegram"]
```

### 生产环境配置示例

```yaml
# ~/.hermes/config.yaml
model:
  default: "anthropic/claude-sonnet-4.6"
  provider: "openrouter"

terminal:
  backend: "docker"
  docker_image: "nikolaik/python-nodejs:python3.11-nodejs20"
  docker_mount_cwd_to_workspace: false
  docker_run_as_host_user: true
  timeout: 300
  container_cpu: 2.0
  container_memory: 4096

compression:
  enabled: true
  threshold: 0.50

memory:
  memory_enabled: true
  user_profile_enabled: true

session_reset:
  mode: "both"
  idle_minutes: 1440

stt:
  enabled: true
  provider: "local"

display:
  cleanup_progress: true
  streaming: true

platform_toolsets:
  cli: ["hermes-cli"]
  telegram: ["hermes-telegram"]
  discord: ["hermes-discord"]
```

### 开发环境配置示例

```yaml
# ~/.hermes/config.yaml
model:
  default: "google/gemini-3-flash-preview"
  provider: "openrouter"

terminal:
  backend: "local"
  cwd: "."
  timeout: 180

agent:
  max_turns: 100
  verbose: true
  reasoning_effort: "high"

compression:
  enabled: true
  threshold: 0.80

display:
  tool_progress: "verbose"
  show_reasoning: true
  streaming: true

platform_toolsets:
  cli: ["hermes-cli"]
```

## 配置验证

验证配置是否正确：

```bash
# 运行诊断
hermes doctor

# 查看当前配置
hermes config list

# 测试配置
hermes --version
```

## 常见配置问题

### 问题 1：API 密钥不生效

**解决方案**：确保密钥在正确的文件中（`~/.hermes/.env`），且没有多余的空格或引号。

```bash
# 检查 .env 文件
cat ~/.hermes/.env

# 验证密钥是否被读取
hermes config list
```

### 问题 2：Docker 终端后端无法启动

**解决方案**：检查 Docker 是否运行，且用户有权限访问 Docker socket。

```bash
# 检查 Docker
docker ps

# 将用户添加到 docker 组
sudo usermod -aG docker $USER
# 重新登录后生效
```

### 问题 3：权限错误

**解决方案**：确保配置目录权限正确。

```bash
# 修复权限
chown -R $USER:$USER ~/.hermes
chmod -R 700 ~/.hermes
```

## 更多信息

- [入门指南](./getting-started.md) - 快速开始使用
- [部署文档](./deployment.md) - 部署方式说明
- [开发者指南](./developer-guide.md) - 开发者相关文档
- [最佳实践](./best-practices.md) - 使用最佳实践
