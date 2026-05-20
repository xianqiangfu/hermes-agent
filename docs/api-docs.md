# Hermes Agent API 文档

本指南介绍 Hermes Agent 的核心 API 和编程接口。

## 目录

- [API 服务器](#api-服务器)
- [OpenAI 兼容 API](#openai-兼容-api)
- [代理 API](#代理-api)
- [工具 API](#工具-api)
- [技能 API](#技能-api)
- [网关 API](#网关-api)
- [配置 API](#配置-api)
- [Python API 参考](#python-api-参考)

## API 服务器

### 启用 API 服务器

API 服务器提供 OpenAI 兼容的接口，可以通过 HTTP 访问 Hermes Agent。

在 `docker-compose.yml` 或环境变量中启用：

```yaml
services:
  gateway:
    environment:
      - API_SERVER_HOST=0.0.0.0
      - API_SERVER_KEY=your-secret-key-here  # 必需的认证密钥
```

或使用环境变量直接运行：

```bash
API_SERVER_HOST=0.0.0.0 API_SERVER_KEY=your-secret-key hermes gateway start
```

### 认证

所有 API 请求都需要在请求头中包含 API 密钥：

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-key-here" \
  -d '{
    "model": "hermes-agent",
    "messages": [
      {"role": "user", "content": "你好，请介绍自己"}
    ]
  }'
```

## OpenAI 兼容 API

### 聊天补全

```
POST /v1/chat/completions
```

请求体：

```json
{
  "model": "hermes-agent",
  "messages": [
    {"role": "system", "content": "你是一个有用的助手"},
    {"role": "user", "content": "你好，请列出当前目录的文件"},
    {"role": "assistant", "content": "我来帮你查看...", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "..."}
  ],
  "stream": true,
  "max_tokens": 2048,
  "temperature": 0.7
}
```

响应（非流式）：

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1699999999,
  "model": "hermes-agent",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "这是当前目录的文件列表..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 150,
    "total_tokens": 250
  }
}
```

流式响应：

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion.chunk",
  "created": 1699999999,
  "model": "hermes-agent",
  "choices": [
    {
      "index": 0,
      "delta": {"content": "你"},
      "finish_reason": null
    }
  ]
}
```

### 列出模型

```
GET /v1/models
```

响应：

```json
{
  "object": "list",
  "data": [
    {
      "id": "hermes-agent",
      "object": "model",
      "created": 1699999999,
      "owned_by": "hermes"
    }
  ]
}
```

## 代理 API

### 初始化代理

```python
from agent import HermesAgent

# 创建代理实例
agent = HermesAgent(
    model="anthropic/claude-opus-4.6",
    tools=["terminal", "file", "web"],
    max_turns=60
)

# 或使用配置文件
agent = HermesAgent.from_config("~/.hermes/config.yaml")
```

### 发送消息

```python
# 单次消息
response = await agent.send_message("你好，请列出当前目录")
print(response.content)

# 流式消息
async for chunk in agent.send_message_stream("写一个 Python 脚本"):
    print(chunk.content, end="")
```

### 对话历史

```python
# 获取对话历史
history = agent.get_conversation_history()
for msg in history:
    print(f"{msg.role}: {msg.content}")

# 重置对话
agent.reset_conversation()
```

### 工具执行回调

```python
def on_tool_call(tool_name, args):
    """工具调用回调"""
    print(f"调用工具: {tool_name}, 参数: {args}")

def on_tool_result(result):
    """工具结果回调"""
    print(f"工具结果: {result}")

agent.set_tool_callbacks(on_tool_call, on_tool_result)
```

## 工具 API

### 内置工具列表

```python
from tools import get_available_tools, get_tool

# 获取所有可用工具
tools = get_available_tools()
for tool in tools:
    print(f"{tool.name}: {tool.description}")

# 获取特定工具
terminal_tool = get_tool("terminal")
```

### 直接使用工具

```python
from tools.terminal import TerminalTool

# 初始化终端工具
terminal = TerminalTool(backend="local", cwd=".")

# 执行命令
result = await terminal("ls -la")
if result.success:
    print(result.output)
else:
    print(f"错误: {result.error}")
```

### 工具结果

```python
from tools.base import ToolResult

# 工具结果结构
result = ToolResult(
    success=True,
    output="命令输出",
    error=None,
    metadata={"duration": 1.23}
)
```

### 创建自定义工具

```python
from typing import Any
from tools.base import BaseTool, ToolResult

class CustomTool(BaseTool):
    """自定义工具"""
    
    name = "custom_tool"
    description = "我的自定义工具"
    
    async def __call__(self, param1: str, param2: int = 42) -> ToolResult:
        """执行工具"""
        try:
            # 实现工具逻辑
            output = f"处理了 {param1} 和 {param2}"
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

### 工具集管理

```python
from toolsets import ToolsetRegistry, get_toolset

# 获取工具集
toolset = get_toolset("hermes-cli")
for tool in toolset:
    print(tool.name)

# 创建自定义工具集
registry = ToolsetRegistry()
registry.register("my-toolset", [CustomTool])
```

## 技能 API

### 加载技能

```python
from skills import Skill, SkillRegistry, load_skill, load_skills_from_dir

# 从文件加载技能
skill = load_skill("~/.hermes/skills/my-skill.md")

# 从目录加载所有技能
skills = load_skills_from_dir("~/.hermes/skills")

# 创建技能注册表
registry = SkillRegistry()
registry.register(skill)
```

### 创建技能

```python
from skills import Skill

# 创建新技能
skill = Skill(
    name="web-scraping",
    description="网页抓取技能",
    content="""
# 网页抓取技能

## 描述
高效抓取和解析网页内容

## 步骤
1. 使用 web_fetch 获取页面
2. 解析 HTML 提取信息
3. 整理并返回结果
    """.strip()
)

# 保存技能
skill.save("~/.hermes/skills/web-scraping.md")
```

### 使用技能

```python
# 向代理提供技能
agent.add_skill(skill)

# 或使用技能注册表
agent.set_skill_registry(registry)
```

### 技能提示注入

```python
# 获取技能的提示片段
prompt = skill.as_prompt()

# 在对话中使用
response = await agent.send_message(
    "抓取这个网页",
    system_prompt_addition=prompt
)
```

## 网关 API

### 启动网关

```python
from gateway import Gateway

# 创建网关
gateway = Gateway(
    platforms=["telegram", "discord"],
    config_file="~/.hermes/config.yaml"
)

# 启动网关
await gateway.start()

# 运行直到停止
try:
    await gateway.run_forever()
finally:
    await gateway.stop()
```

### 平台管理

```python
# 注册新平台
from gateway.platforms.telegram import TelegramPlatform

telegram = TelegramPlatform(
    bot_token="your-bot-token",
    allowed_users=[123456]
)
gateway.add_platform(telegram)

# 列出活动平台
for platform in gateway.platforms:
    print(f"平台: {platform.name}")
```

### 消息处理

```python
from gateway.platforms.base import Message, User

# 发送消息
msg = Message(
    user=User(id="123", name="用户"),
    content="你好",
    platform="telegram"
)
await gateway.send_message(msg)

# 注册消息处理器
async def handle_message(message: Message):
    """处理传入消息"""
    response = await agent.send_message(message.content)
    reply = Message(
        user=message.user,
        content=response.content,
        platform=message.platform
    )
    await gateway.send_message(reply)

gateway.set_message_handler(handle_message)
```

### 会话管理

```python
# 获取用户会话
session = gateway.get_session(user_id="123", platform="telegram")

# 重置会话
gateway.reset_session(user_id="123", platform="telegram")

# 列出所有活动会话
for session_id, session in gateway.sessions.items():
    print(f"会话: {session_id}")
```

## 配置 API

### 加载和访问配置

```python
from hermes_cli.config import load_config, Config

# 加载配置
config = load_config("~/.hermes/config.yaml")

# 访问配置值
model = config.get("model.default", "anthropic/claude-opus-4.6")
backend = config.get("terminal.backend", "local")

# 设置配置值
config.set("model.default", "anthropic/claude-sonnet-4.6")

# 保存配置
config.save()
```

### 配置验证

```python
# 验证配置
errors = config.validate()
if errors:
    for error in errors:
        print(f"配置错误: {error}")
else:
    print("配置有效")
```

### 环境变量

```python
import os
from hermes_constants import ENV_VARS

# 获取环境变量
api_key = os.environ.get("OPENROUTER_API_KEY")

# 或使用辅助函数
from hermes_cli.config import get_env

api_key = get_env("OPENROUTER_API_KEY")
```

## Python API 参考

### agent.HermesAgent

主要的代理类。

```python
class HermesAgent:
    def __init__(
        self,
        model: str = "anthropic/claude-opus-4.6",
        provider: Optional[str] = None,
        tools: Optional[List[str]] = None,
        skills: Optional[List[Skill]] = None,
        max_turns: int = 60,
        config: Optional[Config] = None
    ):
        """初始化 HermesAgent"""
    
    async def send_message(
        self,
        content: str,
        images: Optional[List[bytes]] = None,
        system_prompt: Optional[str] = None,
        system_prompt_addition: Optional[str] = None
    ) -> AgentResponse:
        """发送消息并获取完整响应"""
    
    async def send_message_stream(
        self,
        content: str,
        images: Optional[List[bytes]] = None,
        system_prompt: Optional[str] = None,
        system_prompt_addition: Optional[str] = None
    ) -> AsyncIterable[AgentResponseChunk]:
        """发送消息并获取流式响应"""
    
    def add_tool(self, tool: BaseTool):
        """添加工具"""
    
    def add_skill(self, skill: Skill):
        """添加技能"""
    
    def get_conversation_history(self) -> List[Message]:
        """获取对话历史"""
    
    def reset_conversation(self):
        """重置对话"""
```

### tools.base.BaseTool

所有工具的基类。

```python
class BaseTool:
    name: str
    description: str
    
    async def __call__(self, **kwargs) -> ToolResult:
        """执行工具"""
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的 JSON Schema"""
```

### skills.Skill

技能类。

```python
class Skill:
    def __init__(self, name: str, description: str, content: str):
        """创建技能"""
    
    @classmethod
    def from_file(cls, path: str) -> Skill:
        """从文件加载技能"""
    
    def save(self, path: str):
        """保存技能到文件"""
    
    def as_prompt(self) -> str:
        """获取技能作为提示片段"""
```

### gateway.Gateway

消息网关。

```python
class Gateway:
    def __init__(
        self,
        platforms: Optional[List[str]] = None,
        config_file: Optional[str] = None
    ):
        """创建网关"""
    
    async def start(self):
        """启动网关"""
    
    async def stop(self):
        """停止网关"""
    
    async def run_forever(self):
        """运行直到停止"""
    
    def add_platform(self, platform: Platform):
        """添加平台"""
    
    def get_session(self, user_id: str, platform: str) -> Session:
        """获取用户会话"""
    
    def set_message_handler(self, handler: MessageHandler):
        """设置消息处理器"""
```

### hermes_state.ConversationState

会话状态管理。

```python
class ConversationState:
    def __init__(self):
        """创建会话状态"""
    
    def add_message(self, message: Message):
        """添加消息"""
    
    def get_messages(self) -> List[Message]:
        """获取所有消息"""
    
    def reset(self):
        """重置状态"""
    
    def get_token_count(self) -> int:
        """获取当前 token 计数"""
```

### providers.LLMProvider

LLM 提供商基类。

```python
class LLMProvider:
    async def chat(
        self,
        messages: List[Message],
        model: str,
        stream: bool = False,
        **kwargs
    ) -> Union[LLMResponse, AsyncIterable[LLMResponseChunk]]:
        """聊天补全"""
    
    async def complete(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> LLMResponse:
        """文本补全"""
```

## Web 仪表板 API

### 启动仪表板

```python
from hermes_cli.web_server import WebServer

# 创建并启动服务器
server = WebServer(
    host="127.0.0.1",
    port=8080,
    config_file="~/.hermes/config.yaml"
)

await server.start()
```

### 仪表板端点

```
GET /
GET /api/status
GET /api/conversations
POST /api/conversations/{id}/messages
GET /api/config
POST /api/config
```

## 错误处理

### 异常类

```python
from hermes_cli.errors import (
    HermesError,
    ConfigurationError,
    APIError,
    ToolExecutionError,
    SkillNotFoundError
)

try:
    # 操作
except ConfigurationError as e:
    print(f"配置错误: {e}")
except APIError as e:
    print(f"API 错误: {e}")
    print(f"状态码: {e.status_code}")
except ToolExecutionError as e:
    print(f"工具执行错误: {e}")
```

## 事件系统

### 钩子系统

```python
from hermes_cli.plugins import hookimpl

@hookimpl
def pre_tool_call(tool_name, args):
    """工具调用前"""
    print(f"准备调用 {tool_name}")

@hookimpl
def post_tool_call(tool_name, args, result):
    """工具调用后"""
    print(f"{tool_name} 完成")

@hookimpl
def pre_llm_call(messages):
    """LLM 调用前"""

@hookimpl
def post_llm_call(response):
    """LLM 调用后"""
```

### 注册插件

```python
from hermes_cli.plugins import PluginManager

manager = PluginManager()
manager.register_hooks(my_hooks)
```

## 示例代码

### 完整示例：简单的 CLI 代理

```python
#!/usr/bin/env python3
"""简单的 Hermes Agent CLI 示例"""

import asyncio
from agent import HermesAgent
from hermes_cli.config import load_config

async def main():
    # 加载配置
    config = load_config()
    
    # 创建代理
    agent = HermesAgent.from_config(config)
    
    print("Hermes Agent 控制台")
    print("输入 'quit' 或 'exit' 退出")
    print("-" * 40)
    
    while True:
        try:
            user_input = input("你: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["quit", "exit"]:
                break
            
            if user_input.lower() in ["reset", "clear"]:
                agent.reset_conversation()
                print("对话已重置")
                continue
            
            # 发送消息
            print("代理: ", end="", flush=True)
            async for chunk in agent.send_message_stream(user_input):
                print(chunk.content, end="", flush=True)
            print()
            
        except KeyboardInterrupt:
            print("\n输入 'quit' 或 'exit' 退出")
        except Exception as e:
            print(f"错误: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 完整示例：Telegram 机器人

```python
#!/usr/bin/env python3
"""Telegram 机器人示例"""

import asyncio
import os
from agent import HermesAgent
from gateway import Gateway
from gateway.platforms.telegram import TelegramPlatform
from gateway.platforms.base import Message

async def main():
    # 创建代理
    agent = HermesAgent(
        model=os.environ.get("HERMES_MODEL", "anthropic/claude-opus-4.6"),
        tools=["terminal", "file", "web"]
    )
    
    # 创建 Telegram 平台
    telegram = TelegramPlatform(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        allowed_users=[int(u) for u in os.environ.get("TELEGRAM_ALLOWED_USERS", "").split(",") if u]
    )
    
    # 创建网关
    gateway = Gateway()
    gateway.add_platform(telegram)
    
    # 消息处理器
    async def handle_message(message: Message):
        print(f"收到来自 {message.user.name} 的消息: {message.content}")
        
        async for chunk in agent.send_message_stream(
            message.content,
            system_prompt_addition=f"用户: {message.user.name}"
        ):
            # 流式更新
            pass
        
        # 发送最终响应
        response = await agent.send_message(message.content)
        reply = Message(
            user=message.user,
            content=response.content,
            platform="telegram"
        )
        await gateway.send_message(reply)
    
    gateway.set_message_handler(handle_message)
    
    # 启动网关
    await gateway.start()
    print("Telegram 机器人已启动")
    
    try:
        await gateway.run_forever()
    finally:
        await gateway.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### 完整示例：自定义工具

```python
#!/usr/bin/env python3
"""自定义工具示例"""

import asyncio
from typing import Any
from agent import HermesAgent
from tools.base import BaseTool, ToolResult

class WeatherTool(BaseTool):
    """天气查询工具"""
    
    name = "weather"
    description = "查询指定城市的天气"
    
    async def __call__(self, city: str, unit: str = "celsius") -> ToolResult:
        """查询天气"""
        try:
            # 这里是模拟实现
            # 实际项目中应该调用真实的天气 API
            weather_data = {
                "city": city,
                "temperature": 22 if unit == "celsius" else 72,
                "condition": "晴朗",
                "humidity": 60,
                "unit": unit
            }
            
            output = f"{city} 的天气:\n"
            output += f"温度: {weather_data['temperature']}°{unit[0].upper()}\n"
            output += f"天气: {weather_data['condition']}\n"
            output += f"湿度: {weather_data['humidity']}%"
            
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

async def main():
    # 创建代理
    agent = HermesAgent(tools=["web"])
    
    # 添加自定义工具
    agent.add_tool(WeatherTool())
    
    # 测试
    response = await agent.send_message("查询北京的天气")
    print(response.content)

if __name__ == "__main__":
    asyncio.run(main())
```

## 更多资源

- [入门指南](./getting-started.md)
- [开发者指南](./developer-guide.md)
- [配置文档](./configuration.md)
- [GitHub 仓库](https://github.com/NousResearch/hermes-agent)
