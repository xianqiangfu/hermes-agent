"""OpenRouter 提供商配置文件。

OpenRouter 是一个模型聚合平台，提供统一的 API 访问 200+ 种模型。

本模块实现的主要功能：
- 模型列表缓存，避免重复请求公共目录
- 支持提供商首选项（provider preferences）路由
- 支持 Pareto Code 路由器的最小编码分数配置
- 推理配置透传（reasoning config passthrough）
- xAI Grok 模型的会话 ID 头支持，用于提示缓存固定
- 无需认证即可访问公共模型目录
"""

import logging
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)

# 全局缓存，存储 OpenRouter 模型列表，避免重复请求
_CACHE: list[str] | None = None


class OpenRouterProfile(ProviderProfile):
    """OpenRouter 聚合平台配置文件。

    主要特性：
    - 提供商首选项路由控制
    - 推理配置透传
    - Pareto Code 路由器支持
    - xAI Grok 会话粘性支持
    """

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """从 OpenRouter 公共目录获取模型列表——无需认证。

        OpenRouter 的模型目录是公开的，不需要 API Key 即可访问。
        为了提高性能，结果会被全局缓存。

        注意：工具调用能力的过滤是由 hermes_cli/models.py 通过
        fetch_openrouter_models() → _openrouter_model_supports_tools() 应用的，
        而不是在这里。选择器通过专用的 openrouter 路径提前返回，
        所以这里的过滤是不可达的。

        参数:
            api_key: 未使用，OpenRouter 目录是公开的
            timeout: 请求超时时间（秒）

        返回:
            模型 ID 字符串列表，如果获取失败则返回 None
        """
        global _CACHE  # noqa: PLW0603
        if _CACHE is not None:
            return _CACHE
        try:
            result = super().fetch_models(api_key=None, timeout=timeout)
            if result is not None:
                _CACHE = result
            return result
        except Exception as exc:
            logger.debug("fetch_models(openrouter): %s", exc)
            return None

    def build_extra_body(
        self, *, session_id: str | None = None, **context: Any
    ) -> dict[str, Any]:
        """构建 OpenRouter 特定的 extra_body 字段。

        支持以下功能：
        1. 提供商首选项（provider preferences）：允许用户偏好特定的提供商
        2. Pareto Code 路由器：仅对 openrouter/pareto-code 模型有效，
           设置最小编码分数阈值

        参考文档: https://openrouter.ai/docs/guides/routing/routers/pareto-router

        参数:
            session_id: 会话 ID（在此方法中未使用）
            **context: 上下文参数，可能包含 provider_preferences、model、
                       openrouter_min_coding_score 等

        返回:
            包含 OpenRouter 特定字段的字典
        """
        body: dict[str, Any] = {}
        prefs = context.get("provider_preferences")
        if prefs:
            body["provider"] = prefs

        # Pareto Code 路由器——按模型控制。plugins 块仅对
        # openrouter/pareto-code 有意义；在任何其他模型上发送它没有
        # 记录的效果，并且会在日志中造成混淆。
        model = (context.get("model") or "")
        if model == "openrouter/pareto-code":
            score = context.get("openrouter_min_coding_score")
            if score is not None and score != "":
                try:
                    score_f = float(score)
                except (TypeError, ValueError):
                    score_f = None
                if score_f is not None and 0.0 <= score_f <= 1.0:
                    body["plugins"] = [
                        {"id": "pareto-router", "min_coding_score": score_f}
                    ]
        return body

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        supports_reasoning: bool = False,
        model: str | None = None,
        session_id: str | None = None,
        **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """构建 OpenRouter 特定的 API 参数。

        OpenRouter 将完整的 reasoning_config 字典作为 extra_body.reasoning 传递。

        对于通过 OpenRouter 路由的 xAI Grok 模型，附加 ``x-grok-conv-id`` 头，
        以便 xAI 的提示缓存在多轮对话中保持固定到同一后端服务器。

        参数:
            reasoning_config: 推理配置字典
            supports_reasoning: 模型是否支持推理模式
            model: 模型名称
            session_id: 会话 ID，用于 xAI Grok 模型的缓存粘性
            **context: 其他上下文参数

        返回:
            元组 (extra_body_additions, top_level_kwargs)
        """
        extra_body: dict[str, Any] = {}
        if supports_reasoning:
            if reasoning_config is not None:
                extra_body["reasoning"] = dict(reasoning_config)
            else:
                extra_body["reasoning"] = {"enabled": True, "effort": "medium"}

        extra_headers: dict[str, Any] = {}
        if session_id and model and model.startswith(("x-ai/grok-", "xai/grok-")):
            extra_headers["x-grok-conv-id"] = session_id

        return extra_body, {"extra_headers": extra_headers} if extra_headers else {}


# OpenRouter 提供商配置实例
#
# 字段说明:
# - name: 规范名称 "openrouter"
# - aliases: 别名 "or"，便于快速引用
# - env_vars: 使用 OPENROUTER_API_KEY 环境变量
# - display_name: 显示名称 "OpenRouter"
# - description: 描述信息
# - signup_url: 获取 API Key 的链接
# - base_url: OpenRouter API 基础 URL
# - models_url: 模型列表端点（与基础 URL 分开）
# - fallback_models: 精选的常用模型列表，当实时获取失败时使用
openrouter = OpenRouterProfile(
    name="openrouter",
    aliases=("or",),
    env_vars=("OPENROUTER_API_KEY",),
    display_name="OpenRouter",
    description="OpenRouter — unified API for 200+ models",
    signup_url="https://openrouter.ai/keys",
    base_url="https://openrouter.ai/api/v1",
    models_url="https://openrouter.ai/api/v1/models",
    fallback_models=(
        "anthropic/claude-sonnet-4.6",
        "openai/gpt-5.4",
        "deepseek/deepseek-chat",
        "google/gemini-3-flash-preview",
        "qwen/qwen3-plus",
    ),
)

register_provider(openrouter)
