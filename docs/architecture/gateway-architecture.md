# 网关平台架构

本文档详细描述 Hermes 消息网关的架构设计，包括平台适配器、会话管理、消息路由等核心组件。

## 网关整体架构

```mermaid
graph TB
    subgraph External[外部平台]
        Telegram[Telegram]
        Discord[Discord]
        Slack[Slack]
        WhatsApp[WhatsApp]
        Signal[Signal]
        Weixin[微信]
        Other[其他平台...]
    end
    
    subgraph Gateway[网关核心]
        GatewayRunner[GatewayRunner<br/>主控制器]
        SessionStore[SessionStore<br/>会话存储]
        DeliveryRouter[DeliveryRouter<br/>投递路由器]
        HookRegistry[HookRegistry<br/>事件钩子]
        PlatformRegistry[PlatformRegistry<br/>平台注册中心]
        StreamConsumer[StreamConsumer<br/>流式消费者]
    end
    
    subgraph Adapters[平台适配器]
        BaseAdapter[BasePlatformAdapter<br/>基类]
        TelegramAdapter[TelegramAdapter]
        DiscordAdapter[DiscordAdapter]
        SlackAdapter[SlackAdapter]
        OtherAdapter[其他适配器...]
    end
    
    subgraph Agent[Agent 系统]
        AgentLoop[Agent 循环]
        Skills[技能系统]
        Memory[记忆系统]
    end
    
    %% 连接关系
    External --> Adapters
    Adapters --> Gateway
    Gateway --> Agent
    
    %% 适配器继承
    BaseAdapter <|-- TelegramAdapter
    BaseAdapter <|-- DiscordAdapter
    BaseAdapter <|-- SlackAdapter
    BaseAdapter <|-- OtherAdapter
    
    %% 网关内部连接
    GatewayRunner --> SessionStore
    GatewayRunner --> DeliveryRouter
    GatewayRunner --> HookRegistry
    GatewayRunner --> PlatformRegistry
    GatewayRunner --> StreamConsumer
    
    PlatformRegistry --> BaseAdapter
```

## 平台适配器模式

### 适配器架构

```mermaid
classDiagram
    class BasePlatformAdapter {
        <<abstract>>
        +config: PlatformConfig
        +platform: Platform
        +connected: bool
        +connect() bool
        +disconnect() None
        +send(chat_id, content, reply_to, metadata) SendResult
        +send_image(chat_id, image_url, caption)
        +send_voice(chat_id, audio_path, caption)
        +send_document(chat_id, file_path, caption)
        +start_polling(callback)
        +_mark_connected()
        +_mark_disconnected()
    }
    
    class MessageEvent {
        +text: str
        +message_type: MessageType
        +source: SessionSource
        +raw_message: Any
        +message_id: str
        +media_urls: List[str]
        +reply_to_message_id: str
        +timestamp: datetime
    }
    
    class SessionSource {
        +platform: Platform
        +chat_id: str
        +thread_id: str
        +user_id: str
        +is_dm: bool
    }
    
    class SendResult {
        +success: bool
        +message_id: str
        +error: str
    }
    
    class TelegramAdapter {
        +bot_token: str
        +connect() bool
        +send(chat_id, content, reply_to, metadata) SendResult
        +_handle_update(update)
        +_edit_message(chat_id, message_id, text)
        +_send_draft_message(chat_id, text)
    }
    
    class DiscordAdapter {
        +bot_token: str
        +connect() bool
        +send(chat_id, content, reply_to, metadata) SendResult
        +_handle_message(message)
        +_handle_interaction(interaction)
    }
    
    BasePlatformAdapter <|-- TelegramAdapter
    BasePlatformAdapter <|-- DiscordAdapter
    BasePlatformAdapter --> MessageEvent
    BasePlatformAdapter --> SessionSource
    BasePlatformAdapter --> SendResult
```

### 支持的平台列表

| 平台 | 状态 | 特殊功能 | 适配器文件 |
|------|------|----------|------------|
| Telegram | ✅ 完全支持 | 话题、草稿流式、按钮 | `gateway/platforms/telegram.py` |
| Discord | ✅ 完全支持 | 线程、按钮、技能绑定 | `gateway/platforms/discord.py` |
| Slack | ✅ 完全支持 | Assistant API、线程 | `gateway/platforms/slack.py` |
| WhatsApp | ✅ 支持 | 通过网桥 | `gateway/platforms/whatsapp.py` |
| Signal | ✅ 完全支持 | 加密消息 | `gateway/platforms/signal.py` |
| Weixin | ✅ 完全支持 | 个人微信、群聊 | `gateway/platforms/weixin.py` |
| Matrix | ✅ 完全支持 | 加密房间 | `gateway/platforms/matrix.py` |
| Feishu | ✅ 完全支持 | 富文本、按钮 | `gateway/platforms/feishu.py` |
| API Server | ✅ 完全支持 | HTTP API | `gateway/platforms/api_server.py` |
| Local | ✅ 完全支持 | CLI 交互 | `gateway/platforms/local.py` |

## 会话管理系统

### 会话存储架构

```mermaid
graph TB
    subgraph SessionStore[SessionStore]
        A[会话创建]
        B[会话查找]
        C[会话重置]
        D[会话挂起]
        E[消息存储]
        F[历史加载]
    end
    
    subgraph Storage[存储层]
        SQLite[(SQLite 数据库)]
        JSONL[(JSONL 文件)]
        Meta[(元数据 JSON)]
    end
    
    A --> G{会话存在?}
    G -->|否| H[创建新会话]
    G -->|是| B
    H --> I[生成会话 ID]
    I --> J[初始化会话文件]
    J --> SQLite
    J --> JSONL
    J --> Meta
    B --> K[构建会话键]
    K --> L[查询数据库]
    L -->> B
    E --> M[追加到 JSONL]
    E --> N[插入 SQLite]
    F --> O[从 JSONL 加载]
    F --> P[从 SQLite 加载]
```

### 会话键构建规则

```mermaid
graph LR
    A[SessionSource] --> B{聊天类型}
    B -->|DM| C[agent:main:{platform}:dm:{chat_id}]
    B -->|群聊| D{用户隔离?}
    D -->|是| E[agent:main:{platform}:group:{chat_id}:{user_id}]
    D -->|否| F[agent:main:{platform}:group:{chat_id}]
    B -->|线程| G{线程隔离?}
    G -->|是| H[agent:main:{platform}:thread:{thread_id}:{user_id}]
    G -->|否| I[agent:main:{platform}:thread:{thread_id}]
```

会话键示例：
- `agent:main:telegram:dm:123456789` - Telegram 私聊
- `agent:main:discord:group:987654321:user_123` - Discord 群聊用户隔离
- `agent:main:slack:channel:C0123456789` - Slack 频道共享会话

### 会话生命周期

```mermaid
stateDiagram-v2
    [*] --> NEW: 新建会话
    NEW --> ACTIVE: 首次消息
    ACTIVE --> ACTIVE: 消息交互
    ACTIVE --> SUSPENDED: /stop 命令
    SUSPENDED --> ACTIVE: 新消息
    ACTIVE --> RESETTING: 重置触发
    RESETTING --> ARCHIVED: 归档旧会话
    RESETTING --> NEW: 创建新会话
    ARCHIVED --> [*]
    
    note right of ACTIVE
        检查重置策略:
        - daily (每日定时)
        - idle (空闲超时)
        - both (任一触发)
    end note
```

## 消息路由与投递

### DeliveryRouter 架构

```mermaid
graph TB
    A[DeliveryRouter] --> B[解析投递目标]
    B --> C{目标类型}
    C -->|origin| D[返回消息来源]
    C -->|local| E[本地文件存储]
    C -->|platform| F[平台主频道]
    C -->|platform:chat_id| G[指定聊天]
    C -->|platform:chat:thread| H[指定线程]
    
    D --> I[获取源平台适配器]
    E --> J[写入本地文件]
    F --> K[获取主频道配置]
    G --> L[直接投递]
    H --> L
    
    I --> M[发送消息]
    K --> M
    L --> M
    J --> N[返回文件路径]
    M --> O[记录投递日志]
    N --> O
```

### 投递目标格式

| 目标格式 | 说明 | 示例 |
|----------|------|------|
| `origin` | 返回消息来源 | `origin` |
| `local` | 本地文件存储 | `local` |
| `{platform}` | 平台主频道 | `telegram` |
| `{platform}:{chat_id}` | 指定聊天 | `telegram:123456` |
| `{platform}:{chat_id}:{thread_id}` | 指定线程 | `discord:987654:789012` |

## 流式传输系统

### 流式传输架构

```mermaid
sequenceDiagram
    participant Agent as Agent 循环
    participant Consumer as StreamConsumer
    participant Queue as 队列
    participant Adapter as 平台适配器
    participant User as 用户
    
    Agent->>Consumer: 注册回调
    Agent->>Agent: 生成文本增量
    Agent->>Consumer: on_delta(text)
    Consumer->>Queue: 放入队列
    Consumer->>Consumer: 异步任务处理
    
    loop 消费队列
        Consumer->>Queue: 获取增量
        Consumer->>Consumer: 缓冲文本
        Consumer->>Consumer: 检查阈值/时间
        alt 达到阈值
            Consumer->>Adapter: 发送更新
            alt 草稿模式
                Adapter->>User: 更新草稿消息
            else 编辑模式
                Adapter->>User: 编辑已有消息
            end
        end
    end
    
    Agent->>Consumer: on_final()
    Consumer->>Adapter: 发送最终消息
    Adapter->>User: 显示完成
```

### 流式传输模式

```mermaid
graph TB
    A[流式配置] --> B{传输模式}
    B -->|auto| C{平台支持草稿?}
    B -->|draft| D[草稿模式]
    B -->|edit| E[编辑模式]
    B -->|off| F[禁用流式]
    C -->|是| D
    C -->|否| E
    
    D --> G[原生草稿流式]
    E --> H[渐进式编辑]
    F --> I[完整消息发送]
```

## 平台注册中心

### 插件式平台注册

```mermaid
graph LR
    A[PlatformRegistry] --> B[平台发现]
    A --> C[适配器工厂]
    A --> D[配置验证]
    
    B --> E[扫描插件目录]
    B --> F[加载内置平台]
    
    C --> G[创建适配器实例]
    
    D --> H[检查依赖]
    D --> I[验证配置]
    
    J[插件平台] --> K[注册 PlatformEntry]
    K --> A
```

### PlatformEntry 结构

```python
@dataclass
class PlatformEntry:
    name: str                    # 平台标识符
    label: str                   # 显示名称
    adapter_factory: Callable    # 适配器工厂函数
    check_fn: Optional[Callable] = None  # 依赖检查
    validate_config: Optional[Callable] = None  # 配置验证
    required_env: List[str] = field(default_factory=list)
    install_hint: Optional[str] = None
```

## 事件钩子系统

### HookRegistry 架构

```mermaid
graph TB
    A[HookRegistry] --> B[钩子发现]
    A --> C[钩子加载]
    A --> D[事件触发]
    A --> E[结果收集]
    
    B --> F[扫描 ~/.hermes/hooks/]
    F --> G[读取 HOOK.yaml]
    
    C --> H[导入 handler.py]
    H --> I[注册事件处理器]
    
    D --> J[emit(event, data)]
    J --> K[异步执行钩子]
    
    E --> L[emit_collect(event, data)]
    L --> M[收集返回值]
```

### 支持的事件类型

| 事件 | 触发时机 | 数据 |
|------|----------|------|
| `gateway:startup` | 网关启动 | 配置信息 |
| `session:start` | 新会话创建 | 会话信息 |
| `session:end` | 会话结束 | 会话信息 |
| `session:reset` | 会话重置 | 重置原因 |
| `agent:start` | Agent 开始处理 | 消息事件 |
| `agent:step` | 工具调用步骤 | 步骤详情 |
| `agent:end` | Agent 完成处理 | 响应信息 |
| `command:*` | 斜杠命令 | 命令上下文 |

## 配置管理

### 配置加载流程

```mermaid
graph TB
    A[load_gateway_config] --> B{环境变量}
    B -->|存在| C[应用环境变量]
    B -->|不存在| D[检查配置文件]
    D -->|config.yaml| E[加载 YAML 配置]
    D -->|gateway.json| F[加载 JSON 配置<br/>兼容旧版]
    C --> G[应用默认值]
    E --> G
    F --> G
    G --> H[验证配置]
    H --> I[返回 GatewayConfig]
```

### 配置优先级

```mermaid
graph LR
    A[1. 环境变量] --> B[2. ~/.hermes/config.yaml]
    B --> C[3. ~/.hermes/gateway.json]
    C --> D[4. 内置默认值]
```

## 网关启动流程

```mermaid
sequenceDiagram
    autonumber
    participant CLI as hermes gateway
    participant Config as 配置加载
    participant Registry as 平台注册中心
    participant Adapters as 平台适配器
    participant Session as 会话存储
    participant Gateway as GatewayRunner
    
    CLI->>Config: 加载配置
    Config-->>CLI: GatewayConfig
    
    CLI->>Registry: 发现平台
    Registry-->>CLI: 可用平台列表
    
    CLI->>Adapters: 创建适配器实例
    loop 每个平台
        Adapters->>Adapters: connect()
        Adapters-->>CLI: 连接状态
    end
    
    CLI->>Session: 初始化会话存储
    Session->>Session: 加载现有会话
    Session-->>CLI: 就绪
    
    CLI->>Gateway: 启动网关
    Gateway->>Gateway: 启动事件循环
    Gateway->>Adapters: 开始接收消息
    Gateway-->>CLI: 网关运行中
```

## 相关文档

- [整体架构](./overview.md)
- [对话流程](./conversation-flow.md)
- [定时任务流程](./cron-flow.md)
- [技术栈](../tech-stack.md)
