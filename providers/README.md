# providers/ 模块

模型提供商注册表和抽象基类，定义了 Hermes 支持的所有推理提供商的统一接口。

每个提供商通过 `ProviderProfile` 进行一次声明，其他所有层级（认证解析、传输参数、模型列表、运行时路由）都从这些配置文件读取，而不是维护各自并行的数据结构。

---

## 目录结构

```
providers/
├── base.py         ProviderProfile 数据类 + OMIT_TEMPERATURE 标记
├── __init__.py     注册表：register_provider(), get_provider_profile(), list_providers()
└── README.md       本文件
```

**配置文件本身**作为插件存放在以下位置：
- `plugins/model-providers/<name>/`（本仓库中捆绑的插件）
- `$HERMES_HOME/plugins/model-providers/<name>/`（用户自定义覆盖）

`providers/__init__.py` 中的注册表在第一次调用 `get_provider_profile()` 或 `list_providers()` 时会惰性发现这些插件。有关插件契约和示例，请参阅 `plugins/model-providers/README.md`。

---

## 工作原理

### 核心架构

providers 模块采用**声明式配置**设计模式，将所有提供商相关的信息集中在一个地方管理：

1. **ProviderProfile**：一个数据类，描述提供商的所有行为特征
2. **注册表**：维护所有已注册的提供商配置文件
3. **惰性发现**：首次访问时才扫描并加载插件

### 数据流

```
首次调用 get_provider_profile()
        ↓
_discover_providers() 执行
        ↓
扫描插件目录 → 导入 __init__.py → 调用 register_provider()
        ↓
配置文件存入 _REGISTRY
        ↓
下游模块从注册表读取配置
```

### 与其他模块的集成

注册表在首次访问时填充后，每个下游层级都从中读取：

- `hermes_cli/auth.py`：使用 `PROVIDER_REGISTRY` 扩展每个 API Key 配置文件（跳过 `copilot`、`kimi-coding`、`kimi-coding-cn`、`zai`、`openrouter`、`custom`——这些需要定制的令牌解析）
- `hermes_cli/models.py`：扩展 `CANONICAL_PROVIDERS` 并在 `provider_model_ids()` 内部调用 `profile.fetch_models()`
- `hermes_cli/doctor.py`：为每个 `auth_type="api_key"` 的配置文件添加 `/models` 健康检查
- `hermes_cli/config.py`：将每个 `env_var` 注入 `OPTIONAL_ENV_VARS`，以便设置向导了解这些变量
- `hermes_cli/runtime_provider.py`：读取 `profile.api_mode` 作为 URL 检测未找到时的回退
- `agent/model_metadata.py`：通过 `profile.get_hostname()` 实现主机名到提供商的映射
- `agent/auxiliary_client.py`：首先读取 `profile.default_aux_model`，然后回退到旧的硬编码字典
- `agent/transports/chat_completions.py::_build_kwargs_from_profile()`：在每次调用时调用 `profile.prepare_messages()`、`profile.build_extra_body()` 和 `profile.build_api_kwargs_extras()`
- `run_agent.py`：传递 `provider_profile=<ProviderProfile>`，以便传输层使用配置文件路径而不是旧的标志路径

---

## ProviderProfile 详解

### 核心字段

`ProviderProfile` 是一个数据类，包含以下主要字段类别：

#### 身份标识字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 提供商的规范名称（唯一标识） |
| `api_mode` | str | API 模式，默认为 "chat_completions" |
| `aliases` | tuple | 别名列表，用于兼容旧名称 |

#### 人类可读元数据

| 字段 | 类型 | 说明 |
|------|------|------|
| `display_name` | str | 显示名称，如 "GMI Cloud" — 在选择器/标签中显示 |
| `description` | str | 描述，如 "GMI Cloud (multi-model direct API)" — 选择器副标题 |
| `signup_url` | str | 注册链接，如 "https://www.gmicloud.ai/" — 在设置期间显示 |

#### 认证与端点

| 字段 | 类型 | 说明 |
|------|------|------|
| `env_vars` | tuple | 环境变量名称列表 |
| `base_url` | str | API 基础 URL |
| `models_url` | str | 显式的模型列表端点；回退到 `{base_url}/models` |
| `auth_type` | str | 认证类型：api_key \| oauth_device_code \| oauth_external \| copilot \| aws_sdk |
| `supports_health_check` | bool | 是否支持健康检查，False → doctor 跳过此提供商的 /models 探测 |

#### 模型目录

| 字段 | 类型 | 说明 |
|------|------|------|
| `fallback_models` | tuple | 当实时获取失败时在 /model 选择器中显示的精选列表，只应包含支持工具调用的代理模型 |
| `hostname` | str | 用于 model_metadata.py 中 URL→提供商反向映射的基础主机名，例如 "api.gmi-serving.com"，为空时从 base_url 推导 |

#### 客户端级别特性（在客户端构建时设置一次）

| 字段 | 类型 | 说明 |
|------|------|------|
| `default_headers` | dict | 默认 HTTP 请求头 |

#### 请求级别特性

| 字段 | 类型 | 说明 |
|------|------|------|
| `fixed_temperature` | Any | 温度设置：None = 使用调用者默认值，OMIT_TEMPERATURE = 完全不发送 |
| `default_max_tokens` | int \| None | 默认最大令牌数 |
| `default_aux_model` | str | 用于辅助任务（压缩、视觉等）的廉价模型，空 = 使用主模型 |

### 可覆盖的钩子方法

可以在子类中覆盖这些钩子以处理复杂的提供商特定行为：

| 钩子方法 | 用途 |
|----------|------|
| `get_hostname()` | 基于 URL 的检测——默认从 `base_url` 推导 |
| `prepare_messages(msgs)` | 提供商特定的消息预处理（Qwen 规范化为部分列表，注入 `cache_control`） |
| `build_extra_body(**ctx)` | 提供商特定的 `extra_body`（OpenRouter 提供商首选项、Gemini `thinking_config`） |
| `build_api_kwargs_extras(**ctx)` | `(extra_body_additions, top_level_kwargs)` — Kimi 将 reasoning_effort 放在顶层，Qwen 拆分 `enable_thinking`/`thinking_budget` |
| `fetch_models(*, api_key)` | 实时目录获取——默认使用 Bearer 认证访问 `{models_url or base_url}/models`。为非 REST 提供商（Bedrock）、OAuth 目录（Anthropic）或公共目录（OpenRouter）覆盖 |

---

## 添加新提供商

请参阅 `plugins/model-providers/README.md`——在那里放置一个新目录（或在 `$HERMES_HOME/plugins/model-providers/` 下用于私有插件）。

---

## 使用示例

### 基本使用

```python
from providers import get_provider_profile, list_providers

# 获取单个提供商配置文件
profile = get_provider_profile("anthropic")
if profile:
    print(f"提供商: {profile.display_name}")
    print(f"基础URL: {profile.base_url}")
    print(f"辅助模型: {profile.default_aux_model}")

# 列出所有已注册的提供商
all_providers = list_providers()
for p in all_providers:
    print(f"- {p.name}: {p.description}")
```

### 访问钩子方法

```python
profile = get_provider_profile("openrouter")

# 预处理消息
messages = [{"role": "user", "content": "Hello"}]
processed = profile.prepare_messages(messages)

# 构建额外的请求体
extra_body = profile.build_extra_body(
    session_id="abc123",
    provider_preferences={"order": ["anthropic"]}
)

# 获取模型列表
models = profile.fetch_models(api_key="sk-...")
```

---

## 注意事项

1. **声明式设计**：ProviderProfile 是声明性的——它们描述提供商的行为，不拥有客户端构建、凭据轮换或流式传输，这些仍然在 AIAgent 上

2. **惰性加载**：插件发现是惰性的，直到第一次调用 `get_provider_profile()` 或 `list_providers()` 才会扫描和导入插件

3. **覆盖机制**：用户插件可以通过名称冲突覆盖捆绑插件，后写入者获胜

4. **向后兼容**：为了向后兼容，`providers/*.py` 文件（除了 `base.py` 和 `__init__.py`）仍然通过 `pkgutil.iter_modules` 发现。这允许树外用户将单文件配置文件放入可编辑安装中，而无需插件目录结构。新配置文件应优先使用插件布局

5. **OMIT_TEMPERATURE 标记**：用于表示完全省略 temperature 字段（如 Kimi：由服务器管理）

6. **fetch_models 失败处理**：调用者必须在 `fetch_models()` 返回 None 时始终回退到静态 `_PROVIDER_MODELS` 列表

---

## 配置字段完整参考

完整的字段参考请参见 `providers/base.py` 中的数据类定义。
