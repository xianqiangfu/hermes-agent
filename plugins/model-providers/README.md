# 模型提供商插件

每个子目录都是一个自包含的提供商配置文件插件。目录结构与 `plugins/platforms/` 类似：

```
plugins/model-providers/
├── openrouter/
│   ├── __init__.py      # 注册 ProviderProfile
│   └── plugin.yaml      # 清单：name, kind, version, description
├── anthropic/
│   ├── __init__.py
│   └── plugin.yaml
└── ...
```

---

## 插件发现机制

`providers/__init__.py._discover_providers()` 在第一次调用 `get_provider_profile()` 或 `list_providers()` 时扫描此目录（以及 `$HERMES_HOME/plugins/model-providers/`）。每个 `__init__.py` 被导入并预期调用 `providers.register_provider(profile)`。

位于 `$HERMES_HOME/plugins/model-providers/<name>/` 的用户插件会覆盖同名的捆绑插件——在 `register_provider()` 中后写入者获胜。在那里放置文件即可替换内置插件。

### 发现顺序

1. **捆绑插件**：位于 `<repo>/plugins/model-providers/<name>/`——随 hermes-agent 一起分发
2. **用户插件**：位于 `$HERMES_HOME/plugins/model-providers/<name>/`——可以覆盖任何同名的捆绑配置文件
3. **遗留单文件模块**：位于 `providers/<name>.py`——向后兼容

每个步骤导入其插件，这些插件在模块级别调用 `register_provider()`。后续步骤在名称冲突时获胜。

---

## 添加新提供商

### 步骤 1：创建插件目录结构

```
plugins/model-providers/your-provider/
├── __init__.py
└── plugin.yaml
```

### 步骤 2：编写 `__init__.py`

```python
from providers import register_provider
from providers.base import ProviderProfile

my_provider = ProviderProfile(
    name="your-provider",
    aliases=("alias1", "alias2"),
    display_name="Your Provider",
    description="在设置选择器中显示的单行描述",
    signup_url="https://your-provider.example.com/keys",
    env_vars=("YOUR_PROVIDER_API_KEY", "YOUR_PROVIDER_BASE_URL"),
    base_url="https://api.your-provider.example.com/v1",
    default_aux_model="your-cheap-model",
)

register_provider(my_provider)
```

### 步骤 3：编写 `plugin.yaml`

```yaml
name: your-provider-profile
kind: model-provider
version: 1.0.0
description: 关于提供商的简短描述
author: Your Name
```

### 完成！

无需更改其他任何内容。`auth.py`、`config.py`、`models.py`、`doctor.py`、`model_metadata.py`、`runtime_provider.py` 以及 chat_completions 传输层都会自动从注册表中获取配置。

---

## 复杂配置文件示例

对于具有特殊需求的提供商，可以通过子类化 `ProviderProfile` 并覆盖钩子方法来实现定制行为。

### 示例 1：自定义认证头

```python
"""自定义认证头的提供商示例"""

import json
import urllib.request
from providers import register_provider
from providers.base import ProviderProfile

class CustomAuthProfile(ProviderProfile):
    """使用自定义认证头而不是 Bearer 的提供商"""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """使用自定义认证头获取模型列表"""
        if not api_key:
            return None
        try:
            req = urllib.request.Request(self.models_url or f"{self.base_url}/models")
            req.add_header("X-Custom-Key", api_key)  # 自定义头
            req.add_header("X-Custom-Version", "2024-01-01")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            return [m["id"] for m in data.get("data", []) if isinstance(m, dict) and "id" in m]
        except Exception as exc:
            logger.debug("fetch_models(%s): %s", self.name, exc)
            return None

custom = CustomAuthProfile(
    name="custom",
    env_vars=("CUSTOM_API_KEY",),
    base_url="https://api.custom.example.com/v1",
)

register_provider(custom)
```

### 示例 2：自定义请求体构建

```python
"""具有特殊推理配置的提供商示例"""

from typing import Any
from providers import register_provider
from providers.base import ProviderProfile

class ReasoningProfile(ProviderProfile):
    """需要特殊推理配置格式的提供商"""

    def build_extra_body(
        self, *, session_id: str | None = None, **context: Any
    ) -> dict[str, Any]:
        """构建提供商特定的 extra_body"""
        body: dict[str, Any] = {}
        reasoning_config = context.get("reasoning_config")
        model = context.get("model") or ""

        if reasoning_config:
            # 转换为提供商期望的格式
            if reasoning_config.get("enabled"):
                body["thinking"] = {
                    "mode": "on",
                    "effort": reasoning_config.get("effort", "medium")
                }
            else:
                body["thinking"] = {"mode": "off"}

        # 会话特定配置
        if session_id and "special-model" in model:
            body["session_options"] = {"id": session_id}

        return body

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """分离 extra_body 和顶级参数"""
        extra_body: dict[str, Any] = {}
        top_level: dict[str, Any] = {}

        # 某些提供商将推理配置放在顶层
        if reasoning_config and reasoning_config.get("enabled"):
            top_level["reasoning_effort"] = reasoning_config.get("effort", "medium")

        return extra_body, top_level

reasoning_provider = ReasoningProfile(
    name="reasoning-provider",
    base_url="https://api.reasoning.example.com/v1",
)

register_provider(reasoning_provider)
```

### 示例 3：消息预处理

```python
"""需要消息预处理的提供商示例"""

from typing import Any
from providers import register_provider
from providers.base import ProviderProfile

class MessageTransformProfile(ProviderProfile):
    """需要特殊消息格式的提供商"""

    def prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """预处理消息以适配提供商格式"""
        processed = []
        for msg in messages:
            # 复制原始消息
            new_msg = dict(msg)

            # 提供商特定的转换
            if new_msg.get("role") == "developer":
                # 某些提供商不支持 developer 角色，转换为 system
                new_msg["role"] = "system"

            # 处理多部分内容
            content = new_msg.get("content")
            if isinstance(content, str):
                # 转换为标准化的部分列表格式
                new_msg["content"] = [{"type": "text", "text": content}]

            processed.append(new_msg)

        return processed

transformer = MessageTransformProfile(
    name="transformer",
    base_url="https://api.transformer.example.com/v1",
)

register_provider(transformer)
```

---

## 主要提供商配置文件详解

### Anthropic

- **文件**：`anthropic/__init__.py`
- **特点**：
  - 使用 `x-api-key` 头而不是 Bearer 认证
  - 使用 `anthropic-version` 头
  - API 模式为 `anthropic_messages`
  - 自定义 `fetch_models()` 实现

### OpenRouter

- **文件**：`openrouter/__init__.py`
- **特点**：
  - 聚合器，支持 200+ 模型
  - 支持提供商首选项
  - 自定义 `build_extra_body()` 处理路由偏好
  - 自定义 `build_api_kwargs_extras()` 处理推理配置和 xAI Grok 会话头
  - 公共模型目录，无需认证
  - 模型列表缓存

### Gemini

- **文件**：`gemini/__init__.py`
- **特点**：
  - 支持两种配置：Google AI Studio (API key) 和 Google Cloud Code Assist (OAuth)
  - 自定义 `build_extra_body()` 转换 reasoning_config 为 thinking_config
  - 处理原生格式和 OpenAI 兼容格式

### DeepSeek

- **文件**：`deepseek/__init__.py`
- **特点**：
  - 处理 V4 系列模型的思考模式
  - 防止 reasoning_content 回显错误
  - 自定义 `build_api_kwargs_extras()` 分离 extra_body.thinking 和顶级 reasoning_effort
  - 模型特定的思考能力检测

### Bedrock

- **文件**：`bedrock/__init__.py`
- **特点**：
  - API 模式为 `bedrock_converse`
  - 使用 AWS SDK 认证
  - 无 REST /v1/models 端点
  - `fetch_models()` 返回 None（需要 AWS SDK）

---

## 实际用例

### 用例 1：覆盖内置提供商

要自定义现有提供商而不修改仓库代码，在 `$HERMES_HOME/plugins/model-providers/` 下创建同名的插件：

```
$HERMES_HOME/plugins/model-providers/
└── anthropic/
    ├── __init__.py
    └── plugin.yaml
```

您的版本将覆盖捆绑版本。

### 用例 2：私有提供商插件

在 `$HERMES_HOME/plugins/model-providers/` 下创建您的私有提供商插件，它将自动被发现而无需提交到仓库。

### 用例 3：模型列表定制

覆盖 `fetch_models()` 以过滤或转换模型列表：

```python
def fetch_models(self, *, api_key: str | None = None, timeout: float = 8.0) -> list[str] | None:
    models = super().fetch_models(api_key=api_key, timeout=timeout)
    if models:
        # 只保留支持工具调用的模型
        return [m for m in models if "tool" in m.lower() or "agent" in m.lower()]
    return None
```

---

## 最佳实践

1. **保持配置文件声明性**：ProviderProfile 应该描述提供商的行为，而不是执行操作

2. **使用钩子方法**：通过覆盖钩子方法而不是修改核心代码来处理提供商特定的需求

3. **提供 fallback_models**：始终为 `/model` 选择器提供一个合理的回退模型列表

4. **设置 default_aux_model**：为辅助任务指定一个便宜的模型，以降低成本

5. **日志调试信息**：在自定义钩子方法中使用 `logger.debug()` 记录调试信息

6. **优雅降级**：在 `fetch_models()` 中处理异常并返回 None 以触发回退机制

7. **使用别名**：为向后兼容性添加别名

8. **文档化**：在模块文档字符串中说明配置文件的特殊行为

---

## 注意事项

1. **导入顺序**：用户插件在捆绑插件之后导入，因此可以覆盖它们

2. **模块命名**：捆绑插件使用稳定的导入路径 `plugins.model_providers.<name>`，以便插件内的相对导入工作

3. **用户插件隔离**：用户插件通过 `importlib.util.spec_from_file_location` 加载，具有唯一的模块名称，因此多个 HERMES_HOME 配置文件不会相互别名

4. **向后兼容**：仍然支持遗留的 `providers/<name>.py` 单文件格式，但新提供商应使用插件布局

5. **认证类型**：正确设置 `auth_type` 以确保认证流程正常工作

6. **健康检查**：如果提供商不支持标准的 `/models` 端点，设置 `supports_health_check=False`

7. **温度处理**：对于由服务器管理温度的提供商，使用 `OMIT_TEMPERATURE` 标记
