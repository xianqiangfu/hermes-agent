"""Anthropic (Claude) 提供商配置文件。

本模块实现了 Anthropic 原生 API 的提供商配置文件，具有以下特点：
- 使用 x-api-key 请求头进行认证，而不是标准的 Bearer token
- 需要 anthropic-version 请求头指定 API 版本
- API 模式为 anthropic_messages，使用原生的 Messages API
- 支持通过 ANTHROPIC_API_KEY、ANTHROPIC_TOKEN 或 CLAUDE_CODE_OAUTH_TOKEN 进行认证
- 自定义 fetch_models 实现以适配 Anthropic 的认证方式
- 使用 claude-haiku 作为默认的辅助任务模型以降低成本
"""

import json
import logging
import urllib.request

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)


class AnthropicProfile(ProviderProfile):
    """Anthropic 原生提供商配置文件。

    与标准 OpenAI 兼容端点不同，Anthropic 使用自定义的认证方式：
    - 使用 x-api-key 请求头而不是 Authorization: Bearer
    - 必须提供 anthropic-version 请求头
    - 模型列表端点需要相同的认证方式
    """

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """从 Anthropic API 获取可用模型列表。

        Anthropic 的模型列表端点使用与推理端点相同的认证方式，
        需要 x-api-key 和 anthropic-version 请求头。

        参数:
            api_key: Anthropic API 密钥，如果为 None 则直接返回 None
            timeout: 请求超时时间（秒）

        返回:
            模型 ID 字符串列表，如果获取失败则返回 None
        """
        if not api_key:
            return None
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/models")
            req.add_header("x-api-key", api_key)
            req.add_header("anthropic-version", "2023-06-01")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            return [
                m["id"]
                for m in data.get("data", [])
                if isinstance(m, dict) and "id" in m
            ]
        except Exception as exc:
            logger.debug("fetch_models(anthropic): %s", exc)
            return None


# Anthropic 提供商配置实例
#
# 字段说明:
# - name: 规范名称 "anthropic"
# - aliases: 别名 "claude"、"claude-oauth"、"claude-code"，用于兼容旧配置
# - api_mode: 使用 "anthropic_messages" 原生 API 模式
# - env_vars: 支持三种环境变量进行认证
# - base_url: Anthropic API 基础 URL
# - auth_type: 使用 API Key 认证方式
# - default_aux_model: 使用 Claude Haiku 作为辅助任务的廉价模型
anthropic = AnthropicProfile(
    name="anthropic",
    aliases=("claude", "claude-oauth", "claude-code"),
    api_mode="anthropic_messages",
    env_vars=("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"),
    base_url="https://api.anthropic.com",
    auth_type="api_key",
    default_aux_model="claude-haiku-4-5-20251001",
)

register_provider(anthropic)
