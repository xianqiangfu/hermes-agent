# 依赖关系图

本文档详细描述 Hermes Agent 各模块之间的依赖关系，包括内部模块依赖和外部库依赖。

## 整体依赖关系

```mermaid
graph TB
    subgraph UserLayer[用户接口层]
        CLI[CLI 模块]
        TUI[TUI 界面]
    end
    
    subgraph GatewayLayer[网关层]
        Gateway[消息网关]
        Platforms[平台适配器]
        Session[会话管理]
        Delivery[消息投递]
    end
    
    subgraph AgentLayer[Agent 层]
        AgentLoop[Agent 循环]
        Context[上下文引擎]
        Models[模型适配器]
    end
    
    subgraph ToolSkillLayer[工具/技能层]
        Tools[工具系统]
        Skills[技能系统]
        Memory[记忆系统]
    end
    
    subgraph CronLayer[定时层]
        Cron[Cron 调度]
    end
    
    subgraph UtilLayer[工具层]
        Config[配置管理]
        Logging[日志系统]
        Storage[存储抽象]
    end
    
    %% 用户层依赖
    CLI --> Gateway
    CLI --> AgentLoop
    TUI --> AgentLoop
    
    %% 网关层依赖
    Gateway --> Session
    Gateway --> Delivery
    Gateway --> Platforms
    Gateway --> AgentLoop
    Gateway --> UtilLayer
    
    %% Agent 层依赖
    AgentLoop --> Context
    AgentLoop --> Models
    AgentLoop --> Tools
    AgentLoop --> Skills
    AgentLoop --> Memory
    AgentLoop --> UtilLayer
    
    %% 工具/技能层依赖
    Tools --> UtilLayer
    Skills --> Tools
    Skills --> Memory
    Memory --> Storage
    
    %% 定时层依赖
    Cron --> Gateway
    Cron --> UtilLayer
    
    %% 工具层内部依赖
    Config --> Storage
    Logging --> Config
```

## 核心模块依赖详情

### 网关模块依赖

```mermaid
graph LR
    A[gateway/__init__.py] --> B[gateway/config.py]
    A --> C[gateway/session.py]
    A --> D[gateway/delivery.py]
    A --> E[gateway/hooks.py]
    A --> F[gateway/run.py]
    
    F --> B
    F --> C
    F --> D
    F --> E
    F --> G[gateway/platforms/]
    
    C --> B
    D --> B
    E --> B
    
    G --> H[gateway/platforms/base.py]
    H --> B
```

### Agent 模块依赖

```mermaid
graph LR
    A[agent/__init__.py] --> B[agent/conversation_loop.py]
    A --> C[agent/context_engine.py]
    A --> D[agent/tool_executor.py]
    A --> E[agent/memory_manager.py]
    A --> F[agent/transports/]
    
    B --> C
    B --> D
    B --> E
    B --> F
    
    F --> G[agent/transports/base.py]
    F --> H[agent/transports/anthropic.py]
    F --> I[agent/transports/chat_completions.py]
```

### 工具模块依赖

```mermaid
graph LR
    A[tools/__init__.py] --> B[tools/registry.py]
    A --> C[tools/approval.py]
    A --> D[tools/terminal_tool.py]
    A --> E[tools/file_tools.py]
    A --> F[tools/environments/]
    
    B --> C
    D --> F
    E --> F
    
    F --> G[tools/environments/base.py]
    F --> H[tools/environments/local.py]
    F --> I[tools/environments/docker.py]
    F --> J[tools/environments/ssh.py]
```

## 外部依赖分类

### 核心依赖

```mermaid
mindmap
  root((核心依赖))
    LLM 集成
      anthropic
      openai
      openai>=1.0
    异步框架
      anyio
      aiohttp
      asyncstdlib
    数据处理
      pydantic
      pyyaml
      python-json-logger
    类型支持
      typing-extensions
      typing-inspect
```

### 消息平台依赖

```mermaid
mindmap
  root((平台依赖))
    Telegram
      python-telegram-bot>=20
    Discord
      discord.py>=2.3
    Slack
      slack-bolt
      slack-sdk
    Matrix
      matrix-nio
    Signal
      (外部网桥)
    WhatsApp
      (外部网桥)
```

### 工具执行依赖

```mermaid
mindmap
  root((执行依赖))
    容器
      docker
      docker-sdk
    远程执行
      paramiko
      asyncssh
    Serverless
      modal
    开发环境
      daytona
    其他
      singularity
```

### 记忆与搜索依赖

```mermaid
mindmap
  root((记忆依赖))
    数据库
      sqlite-fts5
      sqlalchemy
    向量搜索
      numpy
      scipy
      sentence-transformers
    外部集成
      honcho
      mem0
```

### CLI 与 TUI 依赖

```mermaid
mindmap
  root((界面依赖))
    CLI
      typer
      rich
      shellingham
    TUI
      textual
      textual-dev
      pygments
    补全
      prompt-toolkit
      python-prompt-toolkit
```

## 可选依赖组

```mermaid
graph TB
    A[hermes] --> B[hermes\[all\]]
    A --> C[hermes\[gateway\]]
    A --> D[hermes\[tools\]]
    A --> E[hermes\[voice\]]
    A --> F[hermes\[dev\]]
    
    B --> C
    B --> D
    B --> E
    
    C --> G[Telegram]
    C --> H[Discord]
    C --> I[Slack]
    
    D --> J[Docker]
    D --> K[SSH]
    D --> L[Modal]
    
    E --> M[OpenAI TTS]
    E --> N[ElevenLabs]
    E --> O[Whisper]
    
    F --> P[pytest]
    F --> Q[black]
    F --> R[mypy]
```

### 依赖组说明

| 依赖组 | 包含内容 | 用途 |
|--------|----------|------|
| `gateway` | 消息平台库 | 运行网关 |
| `tools` | 工具执行后端 | 完整工具支持 |
| `voice` | 语音 TTS/STT | 语音功能 |
| `dev` | 开发工具 | 开发测试 |
| `all` | 全部可选依赖 | 完整功能 |

## 开发依赖

```mermaid
graph TB
    A[开发依赖] --> B[测试]
    A --> C[代码质量]
    A --> D[文档]
    A --> E[构建]
    
    B --> F[pytest]
    B --> G[pytest-asyncio]
    B --> H[pytest-cov]
    B --> I[hypothesis]
    
    C --> J[black]
    C --> K[isort]
    C --> L[mypy]
    C --> M[ruff]
    C --> N[pre-commit]
    
    D --> O[mkdocs]
    D --> P[mkdocs-material]
    
    E --> Q[build]
    E --> R[twine]
    E --> S[wheel]
```

## 依赖版本约束策略

```mermaid
graph LR
    A[版本策略] --> B[核心依赖: ~]
    A --> C[集成依赖: >=,<]
    A --> D[开发依赖: ==]
    
    B --> E[兼容更新]
    C --> F[安全范围]
    D --> G[精确复现]
```

### 版本约束示例

```python
# pyproject.toml 示例
dependencies = [
    "anthropic>=0.20.0,<0.30.0",    # 集成依赖: 范围
    "pydantic~=2.5.0",              # 核心依赖: 兼容更新
    "typer>=0.9.0",                 # CLI: 最低版本
]

[project.optional-dependencies]
dev = [
    "pytest==7.4.3",               # 开发: 精确版本
    "black==23.12.1",
]
```

## 循环依赖防护

```mermaid
graph TB
    A[模块 A] -.->|避免| B[模块 B]
    B -.->|避免| A
    
    C[正确做法] --> D[提取公共模块]
    D --> E[模块 C]
    A --> E
    B --> E
```

### 循环依赖解决方案

| 方案 | 说明 | 适用场景 |
|------|------|----------|
| 提取公共模块 | 将共享代码移到独立模块 | 双向依赖 |
| 依赖注入 | 运行时注入依赖而非导入 | 接口依赖 |
| 事件驱动 | 通过事件解耦 | 通知类依赖 |
| 延迟导入 | 在函数内部导入 | 可选依赖 |

## 依赖图可视化

```mermaid
graph LR
    %% 层级 1: 外部库
    subgraph External
        Anthropic[anthropic]
        OpenAI[openai]
        Pydantic[pydantic]
        Typer[typer]
        Rich[rich]
        PTB[python-telegram-bot]
        DiscordPy[discord.py]
        SQLAlchemy[sqlalchemy]
        NumPy[numpy]
    end
    
    %% 层级 2: 核心工具
    subgraph CoreUtils
        Config[hermes.config]
        Logging[hermes.logging]
        Storage[hermes.storage]
    end
    
    %% 层级 3: 基础模块
    subgraph BaseModules
        Models[hermes.agent.models]
        ToolsBase[hermes.tools.base]
        GatewayBase[hermes.gateway.base]
    end
    
    %% 层级 4: 业务模块
    subgraph BusinessModules
        AgentLoop[hermes.agent.loop]
        Skills[hermes.skills]
        Memory[hermes.memory]
        Session[hermes.gateway.session]
        Delivery[hermes.gateway.delivery]
    end
    
    %% 层级 5: 入口
    subgraph Entry
        CLI[hermes.cli]
        GatewayRunner[hermes.gateway.run]
    end
    
    %% 外部依赖
    Config --> Pydantic
    Logging --> Rich
    Models --> Anthropic
    Models --> OpenAI
    Storage --> SQLAlchemy
    Memory --> NumPy
    
    %% 工具层依赖
    BaseModules --> CoreUtils
    ToolsBase --> Config
    GatewayBase --> Config
    Models --> Config
    
    %% 业务层依赖
    BusinessModules --> BaseModules
    AgentLoop --> Models
    AgentLoop --> ToolsBase
    Skills --> ToolsBase
    Memory --> Storage
    Session --> GatewayBase
    Delivery --> GatewayBase
    
    %% 入口依赖
    Entry --> BusinessModules
    CLI --> AgentLoop
    CLI --> GatewayRunner
    GatewayRunner --> Session
    GatewayRunner --> Delivery
```

## 依赖更新策略

```mermaid
graph TB
    A[依赖更新] --> B[检查更新]
    B --> C{更新类型}
    C -->|安全补丁| D[立即更新]
    C -->|Bug 修复| E[评估后更新]
    C -->|新功能| F[按需更新]
    C -->|破坏性变更| G[谨慎评估]
    
    D --> H[测试]
    E --> H
    F --> H
    G --> I[迁移计划]
    I --> H
    
    H --> J{测试通过?}
    J -->|是| K[提交更新]
    J -->|否| L[回滚]
```

## 相关文档

- [整体架构](./overview.md)
- [目录结构](./directory-tree.md)
- [技术栈](../tech-stack.md)
