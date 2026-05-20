# 平台适配器 (Platform Adapters)

本目录包含 Hermes 消息网关支持的所有消息平台的适配器实现。

## 目录结构

```
gateway/platforms/
├── base.py                  # 平台适配器基类（所有适配器的父类）
├── helpers.py               # 辅助函数
├── _http_client_limits.py   # HTTP 客户端限流
├── ADDING_A_PLATFORM.md     # 添加新平台的详细指南
├── README.md                # 本文件
│
├── telegram.py              # Telegram 适配器
├── discord.py               # Discord 适配器
├── slack.py                 # Slack 适配器
├── whatsapp.py              # WhatsApp 适配器
├── signal.py                # Signal 适配器
├── matrix.py                # Matrix 适配器
├── mattermost.py            # Mattermost 适配器
├── weixin.py                # 微信适配器
├── wecom.py                 # 企业微信适配器
├── wecom_callback.py        # 企业微信回调模式
├── wecom_crypto.py          # 企业微信加密
├── feishu.py                # 飞书适配器
├── feishu_comment.py        # 飞书评论
├── feishu_comment_rules.py  # 飞书评论规则
├── dingtalk.py              # 钉钉适配器
├── bluebubbles.py           # BlueBubbles (iMessage)
├── qqbot/                   # QQ 机器人适配器目录
│   ├── __init__.py
│   ├── adapter.py
│   ├── chunked_upload.py
│   ├── constants.py
│   ├── crypto.py
│   ├── keyboards.py
│   ├── onboard.py
│   └── utils.py
├── yuanbao.py               # 元宝适配器
├── yuanbao_media.py         # 元宝媒体处理
├── yuanbao_proto.py         # 元宝协议
├── yuanbao_sticker.py       # 元宝贴纸
├── api_server.py            # API 服务器平台
├── webhook.py               # Webhook 平台
├── msgraph_webhook.py       # Microsoft Graph Webhook
├── email.py                 # 邮件平台
├── sms.py                   # 短信平台 (Twilio)
└── homeassistant.py         # Home Assistant 平台
```

## 核心概念

### BasePlatformAdapter

所有平台适配器都继承自 `BasePlatformAdapter`，定义了统一的接口：

| 方法 | 必须实现 | 说明 |
|------|---------|------|
| `connect() -> bool` | ✅ | 连接到平台并开始接收消息 |
| `disconnect() -> None` | ✅ | 断开与平台的连接 |
| `send(chat_id, content, ...) -> SendResult` | ✅ | 发送文本消息 |
| `send_typing(chat_id)` | ✅ | 发送输入指示器 |
| `send_image(chat_id, image_url, caption)` | ✅ | 发送图片 |
| `get_chat_info(chat_id) -> dict` | ✅ | 获取聊天信息 |
| `send_document()` | ❌ | 发送文档（有默认实现） |
| `send_voice()` | ❌ | 发送语音（有默认实现） |
| `send_video()` | ❌ | 发送视频（有默认实现） |

### MessageEvent

从平台接收到的消息被转换为 `MessageEvent` 对象：

```python
@dataclass
class MessageEvent:
    text: str                          # 消息文本
    message_type: MessageType          # 消息类型（文本、图片等）
    source: SessionSource              # 消息来源
    raw_message: Any                   # 原始消息对象
    message_id: Optional[str]          # 消息 ID
    platform_update_id: Optional[int]  # 平台更新 ID
    media_urls: List[str]              # 媒体 URL 列表
    media_types: List[str]             # 媒体类型列表
    reply_to_message_id: Optional[str] # 回复的消息 ID
    reply_to_text: Optional[str]       # 被回复的消息文本
    auto_skill: Optional[str | list[str]] # 自动加载的技能
    channel_prompt: Optional[str]      # 频道特定提示
    channel_context: Optional[str]     # 频道上下文
    timestamp: datetime                # 时间戳
```

## 支持的平台列表

### 即时通讯平台

| 平台 | 文件 | 状态 | 特殊功能 |
|------|------|------|---------|
| **Telegram** | `telegram.py` | ✅ 完整支持 | Forum Topics、流式草稿、按钮交互、贴纸缓存 |
| **Discord** | `discord.py` | ✅ 完整支持 | 线程、按钮交互、频道技能绑定、反应表情 |
| **Slack** | `slack.py` | ✅ 完整支持 | Assistant API、线程、按钮交互 |
| **WhatsApp** | `whatsapp.py` | ✅ 完整支持 | 消息投递、富文本 |
| **Signal** | `signal.py` | ✅ 完整支持 | 加密消息、群聊 |
| **Matrix** | `matrix.py` | ✅ 完整支持 | 加密消息、房间 |
| **微信** | `weixin.py` | ✅ 完整支持 | 个人微信、群聊 |
| **企业微信** | `wecom.py` | ✅ 完整支持 | 应用模式、回调模式 |
| **飞书** | `feishu.py` | ✅ 完整支持 | 富文本、按钮、评论处理 |
| **钉钉** | `dingtalk.py` | ✅ 完整支持 | AI 卡片 |
| **Mattermost** | `mattermost.py` | ✅ 完整支持 | 群聊、频道 |
| **BlueBubbles** | `bluebubbles.py` | ✅ 完整支持 | iMessage 网桥 |
| **QQBot** | `qqbot/adapter.py` | ✅ 完整支持 | QQ 机器人、私信/群聊 |
| **元宝** | `yuanbao.py` | ✅ 完整支持 | 元宝平台、私信/群聊 |

### API/Webhook 平台

| 平台 | 文件 | 说明 |
|------|------|------|
| **API Server** | `api_server.py` | HTTP API 服务，可通过 REST API 与网关交互 |
| **Webhook** | `webhook.py` | 通用 Webhook 接收器 |
| **Microsoft Graph** | `msgraph_webhook.py` | Microsoft Graph Webhook 集成 |

### 其他平台

| 平台 | 文件 | 说明 |
|------|------|------|
| **Email** | `email.py` | 邮件收发（IMAP + SMTP） |
| **SMS** | `sms.py` | 短信服务（Twilio） |
| **Home Assistant** | `homeassistant.py` | 智能家居平台集成 |

## 平台适配器开发指南

### 添加新平台的两种方式

1. **插件方式（推荐用于第三方）**
   - 零修改核心代码
   - 在 `~/.hermes/plugins/` 或 `plugins/platforms/` 创建插件
   - 支持动态注册

2. **内置方式（仅核心贡献者）**
   - 直接修改核心代码
   - 详见 [ADDING_A_PLATFORM.md](./ADDING_A_PLATFORM.md)

### 插件方式快速开始

```python
# plugins/platforms/myplatform/__init__.py
from gateway.platform_registry import platform_registry, PlatformEntry

def register(ctx):
    platform_registry.register(PlatformEntry(
        name="myplatform",
        label="My Platform",
        adapter_factory=lambda config: MyPlatformAdapter(config),
        check_fn=lambda: True,  # 检查依赖是否满足
        validate_config=lambda config: bool(config.token),
        required_env=["MYPLATFORM_TOKEN"],
        install_hint="pip install myplatform-sdk",
    ))
```

### 内置方式检查清单

参考 [ADDING_A_PLATFORM.md](./ADDING_A_PLATFORM.md) 的详细检查清单，主要包括：

1. ✅ 创建适配器文件
2. ✅ 在 `Platform` 枚举中注册
3. ✅ 添加配置加载逻辑
4. ✅ 在 `run.py` 中创建适配器工厂
5. ✅ 添加授权检查
6. ✅ 更新系统提示
7. ✅ 添加工具集
8. ✅ 支持 Cron 投递
9. ✅ 支持 send_message 工具
10. ✅ 更新状态显示
11. ✅ 添加设置向导
12. ✅ 文档和测试

## 通用模式与最佳实践

### 1. 消息处理流程

```python
# 平台适配器中的模式
async def _on_message(self, raw_msg):
    # 1. 解析原始消息
    # 2. 过滤自己的消息（防止循环）
    # 3. 构造 MessageEvent
    event = MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=self.build_source(chat_id, user_id),
        raw_message=raw_msg,
        ...
    )
    # 4. 分派给网关处理
    await self.handle_message(event)
```

### 2. 重连逻辑

使用指数退避 + 抖动：

```python
async def _reconnect_loop(self):
    delay = 1
    while self._connected:
        try:
            await self._connect()
            delay = 1  # 重置延迟
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            await asyncio.sleep(delay + random.uniform(0, 1))
            delay = min(delay * 2, 60)  # 最大 60 秒
```

### 3. 敏感信息脱敏

所有日志输出都要脱敏：

```python
# ❌ 不要这样做
logger.info(f"Got message from {phone_number}")

# ✅ 应该这样做
from agent.redact import redact_phone
logger.info(f"Got message from {redact_phone(phone_number)}")
```

### 4. 附件缓存

使用基类提供的缓存方法：

```python
# 从字节缓存图片
image_path = await self.cache_image_from_bytes(image_bytes, "image.jpg")

# 从字节缓存音频
audio_path = await self.cache_audio_from_bytes(audio_bytes, "voice.ogg")
```

### 5. 流式传输支持

两种流式模式：
- **编辑模式**：逐步编辑同一条消息
- **草稿模式**：使用平台原生草稿 API（Telegram Bot API 9.5+）

```python
# 适配器中声明支持的流式模式
class MyPlatformAdapter(BasePlatformAdapter):
    SUPPORTS_STREAMING_DRAFT = True  # 支持原生草稿
```

## 平台特定说明

### Telegram

- 支持 Forum Topics（超级组中的子话题）
- 原生草稿流式传输（Bot API 9.5+）
- 贴纸描述缓存（避免重复分析）
- 支持备用 IP 配置

### Discord

- 自动线程创建
- 频道技能绑定
- 支持 @everyone / @roles 提及（可配置）
- 历史记录回填（用于共享会话）

### Slack

- Assistant API 模式
- 严格提及模式
- 允许机器人消息（可配置）

### 飞书

- 富文本卡片
- 按钮交互
- 评论处理规则
- 事件订阅模式

### 企业微信

- 支持应用模式和回调模式
- 消息加密和解密
- 双向通信

## 测试

每个平台适配器都应该有对应的测试文件：

```bash
# 运行特定平台的测试
python -m pytest tests/gateway/test_telegram.py -v

# 运行所有网关测试
python -m pytest tests/gateway/ -v
```

## 相关文档

- [网关主文档](../README.md) - 网关架构和核心组件说明
- [添加新平台指南](./ADDING_A_PLATFORM.md) - 详细的平台集成步骤
- [配置模块](../config.py) - 平台配置加载逻辑
- [会话管理](../session.py) - 会话存储和上下文管理
