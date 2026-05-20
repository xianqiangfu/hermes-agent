"""Google Gemini 提供商配置文件。

本模块实现了两种 Gemini 配置：
- gemini: Google AI Studio (API key) — 使用 GeminiNativeClient
- google-gemini-cli: Google Cloud Code Assist (OAuth) — 使用 GeminiCloudCodeClient

两者都报告 api_mode="chat_completions"，但使用自定义的原生客户端，
绕过标准的 OpenAI 传输层。配置文件捕获认证和端点元数据用于
auth.py / runtime_provider.py 迁移，并携带 thinking_config 转换钩子，
以便传输层的配置文件路径产生与旧标志路径相同的 extra_body 形状。

主要特点：
- 支持原生 Gemini API 和 OpenAI 兼容 /openai 子路径
- 自动将 reasoning_config 转换为 Gemini 的 thinking_config 格式
- 根据 base_url 自动检测并使用正确的格式
"""

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class GeminiProfile(ProviderProfile):
    """Gemini 配置文件——将 reasoning_config 转换为 extra_body 中的 thinking_config。

    Gemini 有两种 API 格式：
    1. 原生格式：使用 thinking_config 直接放在 extra_body 中
    2. OpenAI 兼容格式：使用 /openai 子路径，thinking_config 放在 extra_body.google.thinking_config

    此类根据 base_url 自动检测使用哪种格式。
    """

    def build_extra_body(
        self, *, session_id: str | None = None, **context: Any
    ) -> dict[str, Any]:
        """构建 Gemini 特定的 extra_body 字段。

        根据 base_url 的类型输出不同格式：
        - 原生格式：extra_body.thinking_config
        - OpenAI 兼容格式：extra_body.extra_body.google.thinking_config

        这是为了镜像旧路径的行为。

        参数:
            session_id: 会话 ID（在此方法中未使用）
            **context: 上下文参数，包含 model、reasoning_config、base_url 等

        返回:
            包含正确格式 thinking_config 的字典
        """
        from agent.transports.chat_completions import (
            _build_gemini_thinking_config,
            _is_gemini_openai_compat_base_url,
            _snake_case_gemini_thinking_config,
        )

        model = context.get("model") or ""
        reasoning_config = context.get("reasoning_config")
        base_url = context.get("base_url") or self.base_url

        # 构建原始的 thinking_config（驼峰命名）
        raw_thinking_config = _build_gemini_thinking_config(model, reasoning_config)
        if not raw_thinking_config:
            return {}

        body: dict[str, Any] = {}
        # 检查是否使用 OpenAI 兼容的 /openai 子路径
        if self.name == "gemini" and _is_gemini_openai_compat_base_url(base_url):
            # OpenAI 兼容格式：需要转换为蛇形命名，并放在 extra_body.google 下
            thinking_config = _snake_case_gemini_thinking_config(raw_thinking_config)
            if thinking_config:
                body["extra_body"] = {"google": {"thinking_config": thinking_config}}
        else:
            # 原生格式：直接使用 thinking_config
            body["thinking_config"] = raw_thinking_config
        return body


# Gemini (Google AI Studio) 提供商配置实例
#
# 字段说明:
# - name: 规范名称 "gemini"
# - aliases: 别名 "google"、"google-gemini"、"google-ai-studio"
# - api_mode: 使用 "chat_completions" 模式（但实际使用自定义客户端）
# - env_vars: 支持 GOOGLE_API_KEY 或 GEMINI_API_KEY 环境变量
# - base_url: Gemini API 基础 URL
# - auth_type: 使用 API Key 认证方式
# - default_aux_model: 使用 Gemini 3 Flash 作为辅助任务的廉价模型
gemini = GeminiProfile(
    name="gemini",
    aliases=("google", "google-gemini", "google-ai-studio"),
    api_mode="chat_completions",
    env_vars=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta",
    auth_type="api_key",
    default_aux_model="gemini-3-flash-preview",
)


# Google Cloud Code Assist (OAuth) 提供商配置实例
#
# 字段说明:
# - name: 规范名称 "google-gemini-cli"
# - aliases: 别名 "gemini-cli"、"gemini-oauth"
# - api_mode: 使用 "chat_completions" 模式
# - env_vars: 空元组（使用 OAuth，无需 API Key）
# - base_url: Cloud Code Assist 内部协议 URL
# - auth_type: 使用外部 OAuth 认证方式
google_gemini_cli = GeminiProfile(
    name="google-gemini-cli",
    aliases=("gemini-cli", "gemini-oauth"),
    api_mode="chat_completions",
    env_vars=(),  # OAuth — no API key
    base_url="cloudcode-pa://google",  # Cloud Code Assist internal scheme
    auth_type="oauth_external",
)

register_provider(gemini)
register_provider(google_gemini_cli)
