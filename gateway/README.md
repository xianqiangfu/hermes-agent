# Hermes 消息网关 (Hermes Messaging Gateway)

消息网关是 Hermes Agent 的核心模块，负责将 AI 助手连接到各种消息平台，实现跨平台的消息接收、处理和投递。

## 目录

- [架构概览](#架构概览)
- [核心组件](#核心组件)
- [支持的平台](#支持的平台)
- [消息流程](#消息流程)
- [会话管理](#会话管理)
- [消息投递](#消息投递)
- [配置说明](#配置说明)
- [开发指南](#开发指南)

## 架构概览

消息网关采用适配器模式，为每个消息平台提供统一的接口：

```
┌─────────────────────────────────────────────────────────────┐
│                      GatewayRunner                           │
│                   (网关运行主控制器)                          │
└────────────────┬────────────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
┌───▼─────┐          ┌────────▼─────────┐
│ Session │          │   Delivery       │
│  Store  │          │    Router        │
└─────────┘          └──────────────────┘
    │                         │
    │              ┌──────────┴──────────┐
    │              │                     │
┌───▼──────────────▼───┐   ┌──────────┬──────────┐
│  BasePlatformAdapter  │   │ Platform │ Platform │
│      (基类)           │   │ Adapter A│ Adapter B│
└──────────────────────┘   └──────────┴──────────┘
         │
    ┌────┴────────────────────────────────────┐
    │                                         │
┌───▼────────┐   ┌──────────┐   ┌──────────┐
│ Telegram   │   │ Discord  │   │ WhatsApp │
│  Adapter   │   │  Adapter │   │  Adapter │
└────────────┘   └──────────┘   └──────────┘
```

### 关键设计原则

1. **统一接口**：所有平台适配器继承 `BasePlatformAdapter`，实现相同的消息发送接口
2. **平台无关**：网关核心逻辑不依赖具体平台，通过 `PlatformRegistry` 实现插件式扩展
3. **动态枚举**：`Platform` 枚举支持运行时动态添加插件平台（通过 `_missing_` 机制），无需修改核心代码
4. **持久化存储**：会话和消息持久化到 SQLite 数据库和 JSONL 文件
5. **流式传输**：支持实时流式输出（编辑模式和原生草稿模式），提升用户体验
6. **多用户隔离**：支持群聊/频道中的用户会话隔离
7. **任务安全**：使用 `contextvars.ContextVar` 实现并发消息处理的会话状态隔离

## 核心组件

### 1. BasePlatformAdapter

平台适配器基类，定义了所有平台适配器必须实现的接口。

**文件位置**: `gateway/platforms/base.py`

**主要方法**：

```python
class BasePlatformAdapter(ABC):
    async def connect(self) -> bool:
        """连接到平台并开始接收消息"""

    async def disconnect(self) -> None:
        """断开与平台的连接"""

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SendResult:
        """发送消息到聊天"""

    async def send_image(self, chat_id: str, image_url: str, caption: Optional[str] = None):
        """发送图片"""

    async def send_voice(self, chat_id: str, audio_path: str, caption: Optional[str] = None):
        """发送语音消息"""

    async def send_video(self, chat_id: str, video_path: str, caption: Optional[str] = None):
        """发送视频"""

    async def send_document(self, chat_id: str, file_path: str, caption: Optional[str] = None):
        """发送文档"""
```

### 2. GatewayConfig

网关配置管理器，负责加载和验证所有平台的配置。

**文件位置**: `gateway/config.py`

**配置优先级** (从高到低)：

1. 环境变量
2. `~/.hermes/config.yaml`
3. `~/.hermes/gateway.json` (兼容旧版)
4. 内置默认值

**主要配置类**：

```python
@dataclass
class GatewayConfig:
    """网关主配置"""
    platforms: Dict[Platform, PlatformConfig]  # 平台配置映射
    default_reset_policy: SessionResetPolicy  # 默认会话重置策略
    reset_by_type: Dict[str, SessionResetPolicy]  # 按类型的重置策略
    reset_by_platform: Dict[Platform, SessionResetPolicy]  # 按平台的重置策略
    streaming: StreamingConfig  # 流式传输配置
    session_store_max_age_days: int  # 会话存储最大保留天数

@dataclass
class PlatformConfig:
    """单个平台配置"""
    enabled: bool  # 是否启用
    token: Optional[str]  # Bot token
    home_channel: Optional[HomeChannel]  # 主频道
    reply_to_mode: str  # 回复模式: off/first/all
    gateway_restart_notification: bool  # 是否发送重启通知
    extra: Dict[str, Any]  # 平台特定配置

@dataclass
class HomeChannel:
    """平台主频道"""
    platform: Platform
    chat_id: str
    name: str
    thread_id: Optional[str] = None  # 线程 ID

@dataclass
class SessionResetPolicy:
    """会话重置策略"""
    mode: str  # daily/idle/both/none
    at_hour: int  # 每日重置时间 (0-23)
    idle_minutes: int  # 空闲超时分钟数
    notify: bool  # 是否通知用户
```

### 3. SessionStore

会话存储管理器，负责会话的生命周期和消息持久化。

**文件位置**: `gateway/session.py`

**主要功能**：

- **会话创建**：为每个消息源创建唯一会话
- **会话重置**：根据重置策略自动或手动重置会话
- **会话挂起**：标记会话为挂起状态
- **会话恢复**：支持网关重启后的会话恢复
- **消息存储**：双重存储（SQLite + JSONL）

```python
class SessionStore:
    def get_or_create_session(
        self,
        source: SessionSource,
        force_new: bool = False
    ) -> SessionEntry:
        """获取或创建会话"""

    def reset_session(self, session_key: str) -> Optional[SessionEntry]:
        """强制重置会话"""

    def suspend_session(self, session_key: str) -> bool:
        """挂起会话"""

    def mark_resume_pending(self, session_key: str, reason: str = "restart_timeout"):
        """标记会话为可恢复状态"""

    def load_transcript(self, session_id: str) -> List[Dict[str, Any]]:
        """加载会话消息历史"""
```

### 4. DeliveryRouter

消息投递路由器，负责将消息路由到正确的目标。

**文件位置**: `gateway/delivery.py`

**支持的目标类型**：

- `origin` - 回到消息来源
- `local` - 本地文件存储
- `platform` - 平台主频道
- `platform:chat_id` - 指定聊天
- `platform:chat_id:thread_id` - 指定线程

```python
class DeliveryRouter:
    async def deliver(
        self,
        content: str,
        targets: List[DeliveryTarget],
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """投递内容到所有指定目标"""

@dataclass
class DeliveryTarget:
    """投递目标"""
    platform: Platform
    chat_id: Optional[str] = None
    thread_id: Optional[str] = None
    is_origin: bool = False
    is_explicit: bool = False
```

### 5. MessageEvent

消息事件类，表示从平台接收到的消息。

**文件位置**: `gateway/platforms/base.py`

```python
@dataclass
class MessageEvent:
    text: str  # 消息文本
    message_type: MessageType  # 消息类型
    source: SessionSource  # 消息来源
    raw_message: Any  # 原始消息对象
    message_id: Optional[str]  # 消息 ID
    platform_update_id: Optional[int]  # 平台更新 ID
    media_urls: List[str]  # 媒体 URL 列表
    media_types: List[str]  # 媒体类型列表
    reply_to_message_id: Optional[str]  # 回复的消息 ID
    reply_to_text: Optional[str]  # 被回复的消息文本
    auto_skill: Optional[str | list[str]]  # 自动加载的技能
    channel_prompt: Optional[str]  # 频道特定提示
    channel_context: Optional[str]  # 频道上下文
    timestamp: datetime  # 时间戳
```

## 支持的平台

网关支持以下消息平台：

### 即时通讯平台

| 平台 | 状态 | 特殊功能 |
|------|------|----------|
| **Telegram** | ✓ 完全支持 | Forum Topics、流式传输预览、按钮交互 |
| **Discord** | ✓ 完全支持 | 线程、按钮交互、频道技能绑定 |
| **Slack** | ✓ 完全支持 | Assistant API、线程、按钮交互 |
| **WhatsApp** | ✓ 通过网桥 | 消息投递、富文本 |
| **Signal** | ✓ 完全支持 | 加密消息、群聊 |
| **Matrix** | ✓ 完全支持 | 加密消息、房间 |
| **Weixin** | ✓ 完全支持 | 个人微信、群聊 |
| **Yuanbao** | ✓ 完全支持 | 元宝、私信/群聊 |
| **QQBot** | ✓ 完全支持 | QQ 机器人、私信/群聊 |
| **Feishu** | ✓ 完全支持 | 飞书、富文本、按钮 |
| **Wecom** | ✓ 完全支持 | 企业微信、应用回调 |
| **DingTalk** | ✓ 完全支持 | 钉钉、AI 卡片 |
| **Mattermost** | ✓ 完全支持 | 群聊、频道 |
| **BlueBubbles** | ✓ 完全支持 | iMessage 网桥 |

### 其他平台

| 平台 | 用途 |
|------|------|
| **Local** | CLI 本地交互 |
| **Email** | 邮件收发 |
| **SMS** | 短信 (Twilio) |
| **ApiServer** | HTTP API 服务 |
| **Webhook** | Webhook 接收 |
| **MsGraphWebhook** | Microsoft Graph Webhook |
| **HomeAssistant** | 智能家居 |

## 消息流程

### 完整消息处理流程

```
1. 平台接收消息
   └─> Telegram Bot / Discord Bot / etc.

2. 消息解析
   └─> 转换为 MessageEvent

3. 会话识别
   └─> build_session_key(source)
   └─> SessionStore.get_or_create_session()

4. 上下文构建
   └─> build_session_context()
   └─> build_session_context_prompt()

5. 消息处理
   └─> GatewayRunner._process_message_with_agent()
   └─> AI Agent 处理

6. 响应发送
   └─> BasePlatformAdapter.send()
   └─> 流式传输 (如果启用)

7. 消息持久化
   └─> SessionStore.append_to_transcript()
```

### 会话键构建规则

会话键是会话的唯一标识，按以下规则构建：

```python
# DM 会话
agent:main:{platform}:dm:{chat_id}[:{thread_id}]

# 群聊/频道会话 (启用用户隔离)
agent:main:{platform}:{chat_type}:{chat_id}[:{thread_id}]:{user_id}

# 群聊/频道会话 (不隔离用户)
agent:main:{platform}:{chat_type}:{chat_id}[:{thread_id}]
```

**示例**：
- `agent:main:telegram:dm:123456789` - Telegram 私聊
- `agent:main:discord:group:987654321:thread:111222333:user_abc` - Discord 群聊中的用户隔离线程
- `agent:main:slack:channel:C0123456789` - Slack 频道 (共享会话)

## 会话管理

### 会话重置策略

网关支持四种会话重置策略：

| 模式 | 说明 |
|------|------|
| `daily` | 在指定时间每天重置 (默认凌晨 4 点) |
| `idle` | 在指定无活动时间后重置 (默认 1440 分钟) |
| `both` | 每日时间和空闲时间任一触发即重置 |
| `none` | 永不自动重置 |

### 配置示例

```yaml
# ~/.hermes/config.yaml

session_reset:
  mode: both  # daily/idle/both/none
  at_hour: 4  # 每日重置时间 (0-23)
  idle_minutes: 1440  # 空闲超时 (分钟)

# 按平台自定义重置策略
reset_by_platform:
  slack:
    mode: idle
    idle_minutes: 60
  discord:
    mode: none
```

### 会话持久化

会话和消息采用双重存储：

1. **SQLite 数据库** (`sessions.db`)
   - 会话元数据
   - 消息记录
   - 索引查询

2. **JSONL 文件** (`{session_id}.jsonl`)
   - 完整消息历史
   - 向后兼容
   - 便于迁移

### 会话状态标志

| 标志 | 用途 |
|------|------|
| `suspended` | 会话被挂起 (如用户执行 `/stop`) |
| `resume_pending` | 网关重启后可恢复的会话 |
| `was_auto_reset` | 会话因超时被自动重置 |
| `is_fresh_reset` | 会话因用户命令被手动重置 |
| `expiry_finalized` | 会话已过期并完成清理 |

## 消息投递

### DeliveryRouter 使用

```python
from gateway.delivery import DeliveryRouter, DeliveryTarget

# 创建路由器
router = DeliveryRouter(config, adapters)

# 投递到多个目标
targets = [
    DeliveryTarget.parse("origin", source=origin),
    DeliveryTarget.parse("telegram:123456789"),
    DeliveryTarget.parse("local"),
]

results = await router.deliver(
    content="Hello from Hermes!",
    targets=targets,
    job_id="daily_report",
    metadata={"job_name": "Daily Report"}
)
```

### 投递目标格式

| 格式 | 说明 |
|------|------|
| `origin` | 回到消息来源 |
| `local` | 本地文件存储 |
| `telegram` | Telegram 主频道 |
| `telegram:123456` | Telegram 指定聊天 |
| `telegram:123456:789` | Telegram 指定线程 |
| `discord` | Discord 主频道 |

### 内容截断

超长内容 (>4000 字符) 会被自动截断，完整内容保存到本地文件：

```
Hermes

[cron output]

... [truncated, full output saved to /home/user/.hermes/cron/output/job_001_20240520_120000.txt]
```

## 配置说明

### 主配置文件

位置: `~/.hermes/config.yaml`

```yaml
# Telegram 配置
telegram:
  enabled: true
  token: ${TELEGRAM_BOT_TOKEN}  # 或直接填写 token
  reply_to_mode: first  # off/first/all
  require_mention: false  # 群聊中是否需要 @ 提及
  allowed_chats: []  # 白名单聊天 ID
  gateway_restart_notification: true

# Discord 配置
discord:
  enabled: true
  token: ${DISCORD_BOT_TOKEN}
  require_mention: false
  channel_skill_bindings:  # 频道技能绑定
    - id: "C0123456789"
      skills: ["weather", "news"]
    - id: "D0987654321"
      skill: "devops"

# 流式传输配置
streaming:
  enabled: true
  transport: auto  # auto/draft/edit/off
  edit_interval: 0.8  # 编辑间隔 (秒)
  buffer_threshold: 24  # 缓冲阈值 (字符)
  cursor: " ▉"  # 光标样式
  fresh_final_after_seconds: 60  # 长响应后发送新消息的阈值

# 会话隔离策略
group_sessions_per_user: true  # 群聊中按用户隔离
thread_sessions_per_user: false  # 线程中按用户隔离

# 会话存储
session_store_max_age_days: 90  # 会话保留天数 (0=禁用修剪)

# STT (语音转文字)
stt:
  enabled: true  # 自动转录语音消息

# 语音自动 TTS
voice:
  auto_tts: false  # 自动播放语音回复
```

### 环境变量配置

```bash
# Telegram
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_HOME_CHANNEL="123456789"
export TELEGRAM_REPLY_TO_MODE="first"

# Discord
export DISCORD_BOT_TOKEN="your_bot_token"
export DISCORD_HOME_CHANNEL="123456789"

# WhatsApp
export WHATSAPP_ENABLED="true"
export WHATSAPP_HOME_CHANNEL="123456789"

# Slack
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_HOME_CHANNEL="C0123456789"

# 更多环境变量... (见 config.py)
```

### 平台特定配置

每个平台可在 `extra` 字段中设置特定配置：

```yaml
platforms:
  telegram:
    extra:
      allowed_topics: []  # 允许的话题 ID
      ignored_threads: []  # 忽略的线程 ID
      guest_mode: false  # 访客模式
      disable_link_previews: false  # 禁用链接预览
      fallback_ips: []  # 失败备用 IP

  discord:
    extra:
      allowed_channels: []  # 白名单频道
      ignored_channels: []  # 黑名单频道
      free_response_channels: []  # 自由回复频道
      auto_thread: true  # 自动创建线程
      reactions: true  # 启用表情反应

  slack:
    extra:
      require_mention: false  # 需要 @ 提及
      strict_mention: false  # 严格提及模式
      allow_bots: false  # 允许机器人消息
      free_response_channels: []  # 自由回复频道
      allowed_channels: []  # 白名单频道
```

## 开发指南

### 添加新平台适配器

1. **创建适配器文件**

```python
# gateway/platforms/myservice.py
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType
from gateway.config import Platform, PlatformConfig

class MyServiceAdapter(BasePlatformAdapter):
    def __init__(self, config: PlatformConfig, platform: Platform):
        super().__init__(config, platform)
        # 初始化你的平台客户端

    async def connect(self) -> bool:
        # 连接到平台
        self._mark_connected()
        return True

    async def disconnect(self) -> None:
        # 断开连接
        self._mark_disconnected()

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SendResult:
        # 发送消息
        return SendResult(success=True, message_id="msg_id")
```

2. **在平台枚举中注册**

```python
# gateway/config.py
class Platform(Enum):
    # ... 现有平台
    MYSERVICE = "myservice"
```

3. **添加配置支持**

```python
# gateway/config.py
_PLATFORM_CONNECTED_CHECKERS = {
    # ... 现有检查器
    Platform.MYSERVICE: lambda cfg: bool(cfg.token),
}

def _apply_env_overrides(config: GatewayConfig) -> None:
    # ... 添加环境变量处理
    myservice_token = os.getenv("MYSERVICE_TOKEN")
    if myservice_token:
        if Platform.MYSERVICE not in config.platforms:
            config.platforms[Platform.MYSERVICE] = PlatformConfig()
        config.platforms[Platform.MYSERVICE].enabled = True
        config.platforms[Platform.MYSERVICE].token = myservice_token
```

4. **创建网关注册**

```python
# gateway/platforms/__init__.py
__all__ = [
    # ...
    "MyServiceAdapter",
]
```

### 测试平台适配器

```python
import pytest
from gateway.platforms.myservice import MyServiceAdapter
from gateway.config import PlatformConfig, Platform

@pytest.mark.asyncio
async def test_myservice_connect():
    config = PlatformConfig(enabled=True, token="test_token")
    adapter = MyServiceAdapter(config, Platform.MYSERVICE)
    assert await adapter.connect() is True

@pytest.mark.asyncio
async def test_myservice_send():
    config = PlatformConfig(enabled=True, token="test_token")
    adapter = MyServiceAdapter(config, Platform.MYSERVICE)
    await adapter.connect()

    result = await adapter.send(
        chat_id="test_chat",
        content="Hello, world!"
    )
    assert result.success is True
```

### 扩展会话上下文

在 `build_session_context_prompt` 中添加平台特定信息：

```python
# gateway/session.py
elif context.source.platform == Platform.MYSERVICE:
    lines.append("")
    lines.append(
        "**Platform notes:** You are running inside MyService. "
        "Support custom features..."
    )
```

## 辅助模块

### HookRegistry — 事件钩子系统

**文件位置**: `gateway/hooks.py`

事件钩子系统提供轻量级的事件驱动机制，在网关生命周期的关键节点触发自定义处理逻辑。

**支持的事件类型**：

| 事件 | 触发时机 |
|------|----------|
| `gateway:startup` | 网关进程启动 |
| `session:start` | 新会话创建（首次消息） |
| `session:end` | 会话结束（用户执行 /new 或 /reset） |
| `session:reset` | 会话重置完成 |
| `agent:start` | Agent 开始处理消息 |
| `agent:step` | 工具调用循环中的每一步 |
| `agent:end` | Agent 完成处理 |
| `command:*` | 任意斜杠命令（通配符匹配） |

**钩子发现机制**：扫描 `~/.hermes/hooks/` 目录，每个钩子子目录包含：
- `HOOK.yaml`：元数据（名称、描述、事件列表）
- `handler.py`：处理函数（支持同步和异步）

```python
from gateway.hooks import HookRegistry

registry = HookRegistry()
registry.discover_and_load()

# 触发事件（忽略返回值）
await registry.emit("agent:start", {"platform": "telegram", ...})

# 触发事件（收集返回值，用于决策类钩子）
results = await registry.emit_collect("command:reset", context)
```

### PlatformRegistry — 平台注册中心

**文件位置**: `gateway/platform_registry.py`

允许平台适配器（内置和插件）自注册，网关无需硬编码 if/elif 链即可发现和实例化适配器。

**插件端使用**：

```python
from gateway.platform_registry import platform_registry, PlatformEntry

platform_registry.register(PlatformEntry(
    name="irc",
    label="IRC",
    adapter_factory=lambda cfg: IRCAdapter(cfg),
    check_fn=check_requirements,
    validate_config=lambda cfg: bool(cfg.extra.get("server")),
    required_env=["IRC_SERVER"],
    install_hint="pip install irc",
))
```

**网关端使用**：

```python
adapter = platform_registry.create_adapter("irc", platform_config)
```

**PlatformEntry 关键属性**：

| 属性 | 用途 |
|------|------|
| `name` | 配置标识符（如 "irc"） |
| `label` | 人类可读名称（如 "IRC"） |
| `adapter_factory` | 适配器工厂函数 |
| `check_fn` | 依赖可用性检查 |
| `validate_config` | 配置验证 |
| `env_enablement_fn` | 环境变量自动启用 |
| `apply_yaml_config_fn` | YAML 配置桥接 |
| `standalone_sender_fn` | 独立进程消息发送 |
| `cron_deliver_env_var` | Cron 投递环境变量 |

### GatewayStreamConsumer — 流式传输消费器

**文件位置**: `gateway/stream_consumer.py`

将同步的 Agent 流式回调桥接到异步的平台消息递送。

**工作流程**：
1. Agent 在工作线程中同步调用 `stream_delta_callback(text)`
2. `on_delta()` 接收增量文本（线程安全，同步）
3. 通过 `queue.Queue` 队列传递到 asyncio 任务
4. 异步 `run()` 任务缓冲、限速、逐步编辑平台消息

**传输模式**：

| 模式 | 说明 |
|------|------|
| `auto` | 优先使用原生草稿流式（Telegram Bot API 9.5+），不支持时回退到编辑模式 |
| `draft` | 显式请求原生草稿流式 |
| `edit` | 渐进式 editMessageText（默认/传统行为） |
| `off` | 禁用流式传输 |

### SessionContext — 会话上下文变量

**文件位置**: `gateway/session_context.py`

使用 Python `contextvars.ContextVar` 替代 `os.environ` 实现任务级会话状态隔离。

**设计动机**：网关通过 `asyncio` 并发处理消息。旧代码使用 `os.environ` 存储会话状态，导致并发消息之间状态互相覆盖。`ContextVar` 值是任务局部的，每个 asyncio 任务获得独立副本，避免干扰。

**公共接口**：

```python
from gateway.session_context import get_session_env, set_session_vars, clear_session_vars

# 读取会话环境变量（兼容旧代码）
platform = get_session_env("HERMES_SESSION_PLATFORM", "")

# 设置会话变量（任务局部）
set_session_vars(platform="telegram", chat_id="123456", ...)

# 清除会话变量
clear_session_vars()
```

### 频道目录 (ChannelDirectory)

**文件位置**: `gateway/channel_directory.py`

缓存各平台可达频道/联系人的映射表。网关启动时构建，每 5 分钟刷新，保存到 `~/.hermes/channel_directory.json`。

`send_message` 工具使用此文件实现 `action="list"` 功能和人友好的频道名称到数字 ID 的解析。

### 会话镜像 (Mirror)

**文件位置**: `gateway/mirror.py`

跨平台消息投递时，将"投递镜像"记录追加到目标会话的转录中，使接收端 Agent 具有已发送内容的上下文。

独立运行——可在 CLI、Cron 和网关上下文中工作，无需完整的 SessionStore 机制。

### DM 配对系统 (Pairing)

**文件位置**: `gateway/pairing.py`

基于配对码的新用户审批流程，替代静态用户 ID 白名单。

**安全特性**：
- 8 位配对码，32 字符无歧义字母表（排除 0/O/1/I）
- `secrets.choice()` 密码学随机
- 1 小时配对码过期
- 每个平台最多 3 个待处理配对码
- 速率限制：每用户每 10 分钟 1 次请求
- 5 次审批失败后锁定 1 小时
- 文件权限：chmod 0600
- 配对码永不输出到 stdout

### 显示配置 (DisplayConfig)

**文件位置**: `gateway/display_config.py`

提供 `resolve_display_setting()` —— 读取显示设置的唯一入口，支持平台特定覆盖和合理默认值。

**解析优先级**（首个非 None 值胜出）：
1. `display.platforms.<platform>.<key>` — 显式平台覆盖
2. `display.<key>` — 全局用户设置
3. `_PLATFORM_DEFAULTS[<platform>][<key>]` — 内置平台默认值
4. `_GLOBAL_DEFAULTS[<key>]` — 内置全局默认值

### 内存监控 (MemoryMonitor)

**文件位置**: `gateway/memory_monitor.py`

周期性记录网关进程内存使用情况。每 5 分钟发出一条 `[MEMORY] ...` 结构化日志行，便于诊断长时间运行网关的内存泄漏。

支持 `resource`（Linux/macOS 标准库）和 `psutil`（Windows 回退），两者均不可用时自动禁用。

### 斜杠命令访问控制 (SlashAccess)

**文件位置**: `gateway/slash_access.py`

在现有平台白名单基础上增加第二维度：允许与网关通信的用户中，谁能运行哪些斜杠命令。

两个列表（DM / 群聊作用域）：
- `allow_admin_from`：获取所有斜杠命令的管理员用户 ID
- `user_allowed_commands`：非管理员用户可运行的命令名列表

**向后兼容**：未设置 `allow_admin_from` 时，斜杠命令门控完全禁用，所有允许用户可运行所有命令。

### 表情贴纸缓存 (StickerCache)

**文件位置**: `gateway/sticker_cache.py`

缓存 Telegram 表情贴纸的描述文本，以 `file_unique_id` 为键。用户发送贴纸时通过视觉工具描述贴纸内容并缓存，避免重复分析。

缓存位置：`~/.hermes/sticker_cache.json`

### WhatsApp 身份解析 (WhatsAppIdentity)

**文件位置**: `gateway/whatsapp_identity.py`

统一 WhatsApp 发送者身份标识的辅助模块。WhatsApp 网桥可能以两种 JID 形式呈现同一用户（LID 形式和电话号码形式），此模块将两者归约为单一稳定身份。

**公共接口**：
- `normalize_whatsapp_identifier()` — 剥离 JID/LID 语法
- `canonical_whatsapp_identifier()` — 通过网桥映射文件返回规范身份
- `expand_whatsapp_aliases()` — 返回标识符的完整别名集

### 运行时状态 (Status)

**文件位置**: `gateway/status.py`

提供基于 PID 文件的网关守护进程运行检测。PID 文件位于 `{HERMES_HOME}/gateway.pid`，供 `send_message` 工具的 `check_fn` 在 CLI 中判断网关可用性。

### 关闭取证 (ShutdownForensics)

**文件位置**: `gateway/shutdown_forensics.py`

网关收到 SIGTERM/SIGINT 时捕获关闭上下文。提供快速（<10ms）非阻塞的 `snapshot_shutdown_context()` 供信号处理器立即记录，以及 `spawn_async_diagnostic()` 进行异步诊断。

### 运行时元数据页脚 (RuntimeFooter)

**文件位置**: `gateway/runtime_footer.py`

在 Agent 回合的最终消息中追加紧凑的运行时元数据页脚（模型、上下文百分比、工作目录）。默认关闭，通过 `display.runtime_footer.enabled: true` 启用。

### 重启常量 (Restart)

**文件位置**: `gateway/restart.py`

共享的网关重启常量和解析辅助函数。`GATEWAY_SERVICE_RESTART_EXIT_CODE = 75` 对应 `EX_TEMPFAIL`，请求服务管理器在优雅排空/重载后重启网关。

## 故障排查

### 常见问题

1. **平台连接失败**
   - 检查 token/api_key 是否正确
   - 检查网络连接和代理设置
   - 查看网关日志 (`gateway.log`)

2. **消息不回复**
   - 检查 `require_mention` 设置
   - 检查白名单/黑名单配置
   - 查看会话是否被挂起

3. **会话丢失**
   - 检查重置策略配置
   - 查看会话存储路径
   - 检查磁盘空间

### 调试模式

```bash
# 启动网关时启用详细日志
hermes gateway --debug

# 查看运行时状态
cat ~/.hermes/runtime/status.json

# 查看会话信息
cat ~/.hermes/sessions/sessions.json
```

## 相关文档

- [平台适配器开发指南](gateway/platforms/ADDING_A_PLATFORM.md)
- [配置参考](../README.md#configuration)
- [会话管理详解](#会话管理)
- [消息投递 API](#消息投递)

## 许可证

消息网关模块是 Hermes Agent 项目的一部分，遵循项目许可证。