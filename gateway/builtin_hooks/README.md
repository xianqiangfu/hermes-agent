# 内置钩子 (Built-in Hooks)

本目录包含 Hermes 消息网关的内置事件钩子。

## 目录结构

```
gateway/builtin_hooks/
├── __init__.py     # 空模块，预留扩展
└── README.md       # 本文件
```

## 什么是事件钩子？

事件钩子是 Hermes 网关的轻量级扩展机制，允许在网关生命周期的关键节点插入自定义逻辑，而无需修改核心代码。

### 支持的事件类型

| 事件 | 触发时机 | context 包含 |
|------|---------|-------------|
| `gateway:startup` | 网关进程启动时 | `{platforms: [...]}` |
| `session:start` | 新会话创建时（首次消息） | `{session_id, source, platform}` |
| `session:end` | 会话结束时（用户执行 `/new` 或 `/reset`） | `{session_id, source}` |
| `session:reset` | 会话重置完成时 | `{session_id, old_session_id, source}` |
| `agent:start` | Agent 开始处理消息时 | `{session_id, message, source}` |
| `agent:step` | 工具调用循环的每一步 | `{session_id, step, tool_calls}` |
| `agent:end` | Agent 完成处理时 | `{session_id, response, duration}` |
| `command:*` | 任意斜杠命令执行时 | `{command, args, session_id}` |
| `command:reset` | `/reset` 命令执行时 | 同上 |
| `command:new` | `/new` 命令执行时 | 同上 |
| `command:stop` | `/stop` 命令执行时 | 同上 |

## 钩子目录结构

### 用户钩子位置

用户自定义钩子放在 `~/.hermes/hooks/` 目录：

```
~/.hermes/hooks/
├── my_hook/
│   ├── HOOK.yaml        # 钩子元数据
│   └── handler.py       # 处理函数
└── another_hook/
    ├── HOOK.yaml
    └── handler.py
```

### HOOK.yaml 格式

```yaml
name: my_hook
description: "我的自定义钩子，用于监控 session 创建"
events:
  - "session:start"
  - "session:end"
```

### handler.py 格式

处理函数可以是同步或异步的：

```python
# 同步处理器
def handle(event_type: str, context: dict):
    print(f"Got event {event_type} with context: {context}")

# 异步处理器（推荐）
async def handle(event_type: str, context: dict):
    # 可以执行异步操作
    await send_alert(event_type, context)
```

### 通配符匹配

使用 `command:*` 匹配所有命令事件：

```yaml
name: command_logger
description: "记录所有斜杠命令"
events:
  - "command:*"
```

匹配顺序：
1. 精确匹配（如 `command:reset`）优先
2. 然后是通配符匹配（如 `command:*`）

## 完整示例

### 示例 1：命令审计钩子

```yaml
# ~/.hermes/hooks/audit/HOOK.yaml
name: audit
description: "审计所有命令执行"
events:
  - "command:*"
```

```python
# ~/.hermes/hooks/audit/handler.py
import json
from pathlib import Path
from datetime import datetime

AUDIT_LOG = Path("~/.hermes/audit.log").expanduser()

async def handle(event_type: str, context: dict):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "command": context.get("command"),
        "args": context.get("args"),
        "session_id": context.get("session_id"),
        "platform": context.get("source", {}).get("platform"),
    }

    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

### 示例 2：会话通知钩子

```yaml
# ~/.hermes/hooks/session_notify/HOOK.yaml
name: session_notify
description: "新会话创建时发送通知"
events:
  - "session:start"
```

```python
# ~/.hermes/hooks/session_notify/handler.py
import os
import requests

async def handle(event_type: str, context: dict):
    webhook_url = os.getenv("SESSION_WEBHOOK_URL")
    if not webhook_url:
        return

    source = context.get("source", {})
    message = (
        f"🆕 新会话创建\n"
        f"平台: {source.get('platform')}\n"
        f"聊天: {source.get('chat_id')}\n"
        f"用户: {source.get('user_id', '未知')}"
    )

    try:
        requests.post(webhook_url, json={"text": message})
    except Exception as e:
        print(f"Failed to send webhook: {e}")
```

### 示例 3：决策钩子（使用 emit_collect）

某些事件支持收集返回值来影响网关行为：

```yaml
name: command_policy
description: "命令执行策略"
events:
  - "command:reset"
```

```python
def handle(event_type: str, context: dict):
    # 返回值会被收集
    source = context.get("source", {})
    platform = source.get("platform")

    # 示例：只允许在 Telegram 上执行 reset
    if platform != "telegram":
        return {"allowed": False, "reason": "Not allowed on this platform"}

    return {"allowed": True}
```

## 错误处理

- 钩子中的异常**不会**阻塞主管道
- 异常会被捕获并打印到 stdout
- 加载失败的钩子会被跳过并记录错误

```
[hooks] Error loading hook bad_hook: Invalid HOOK.yaml
[hooks] Error in handler for 'session:start': Connection refused
```

## 内置钩子扩展点

`gateway/hooks.py` 中的 `_register_builtin_hooks()` 方法是预留的扩展点，用于注册内置钩子。

如果要添加内置钩子，实现方式如下：

```python
# gateway/builtin_hooks/my_hook.py
def handle(event_type: str, context: dict):
    # 内置钩子逻辑
    pass
```

然后在 `HookRegistry._register_builtin_hooks()` 中注册：

```python
def _register_builtin_hooks(self) -> None:
    from .builtin_hooks.my_hook import handle as my_hook_handle
    self._handlers.setdefault("agent:start", []).append(my_hook_handle)
    self._loaded_hooks.append({
        "name": "my_builtin_hook",
        "description": "内置钩子示例",
        "events": ["agent:start"],
        "path": "builtin",
    })
```

## 与网关的集成

钩子在 `gateway/run.py` 中被加载和使用：

```python
# 启动时加载钩子
hook_registry = HookRegistry()
hook_registry.discover_and_load()

# 触发事件
await hook_registry.emit("gateway:startup", {"platforms": connected_platforms})

# 在消息处理流程中
await hook_registry.emit("session:start", {"session_id": ..., "source": ...})
await hook_registry.emit("agent:start", {"session_id": ..., "message": ...})
```

## 开发与调试

### 测试钩子

```python
# 快速测试你的钩子
from gateway.hooks import HookRegistry

registry = HookRegistry()
registry.discover_and_load()

# 列出已加载的钩子
print("Loaded hooks:", registry.loaded_hooks)

# 手动触发测试
await registry.emit("session:start", {"test": "data"})
```

### 日志调试

钩子的加载和执行会输出日志：

```
[hooks] Loaded hook 'audit' for events: ['command:*']
[hooks] Loaded hook 'session_notify' for events: ['session:start']
```

## 安全注意事项

1. **钩子代码完全可信**：钩子在网关进程中运行，可以访问所有内存状态
2. **不要安装来源不明的钩子**：仔细审查第三方钩子代码
3. **环境变量保护**：钩子可以访问所有环境变量，包括敏感信息
4. **权限限制**：确保 `~/.hermes/hooks/` 目录的权限适当（建议 0700）

## 高级模式

### 状态保持

钩子模块在进程生命周期内保持加载，因此可以保持状态：

```python
# handler.py
from collections import defaultdict

# 模块级变量，在多次调用间保持
event_counts = defaultdict(int)

async def handle(event_type: str, context: dict):
    event_counts[event_type] += 1
    print(f"Event {event_type} count: {event_counts[event_type]}")
```

### 使用 Pydantic 模型

钩子支持使用 Pydantic 进行数据验证，因为模块在加载前已经注册到 `sys.modules`：

```python
from pydantic import BaseModel

class SessionContext(BaseModel):
    session_id: str
    source: dict

async def handle(event_type: str, context: dict):
    # 安全地解析和验证
    ctx = SessionContext(**context)
    print(ctx.session_id)
```

## 相关文档

- [网关主文档](../README.md) - 网关架构概览
- [钩子模块源码](../hooks.py) - HookRegistry 实现
