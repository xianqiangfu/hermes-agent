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
2. **平台无关**：网关核心逻辑不依赖具体平台，易于扩展新平台
3. **持久化存储**：会话和消息持久化到 SQLite 数据库和 JSONL 文件
4. **流式传输**：支持实时流式输出，提升用户体验
5. **多用户隔离**：支持群聊/频道中的用户会话隔离

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