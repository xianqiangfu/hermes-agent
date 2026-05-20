"""OpenAI Codex (Responses API) 提供商配置文件。

OpenAI Codex 是 OpenAI 的代码生成模型，本配置文件用于通过
ChatGPT 后端 API 访问 Codex 功能。

主要特点：
- 使用专用的 codex_responses API 模式
- 通过外部 OAuth 进行认证，不使用 API Key
- 连接到 ChatGPT 后端 API 端点
- 支持旧版名称别名以保持向后兼容
"""

from providers import register_provider
from providers.base import ProviderProfile


# OpenAI Codex 提供商配置实例
#
# 字段说明:
# - name: 规范名称 "openai-codex"
# - aliases: 别名 "codex"、"openai_codex"，用于兼容旧配置
# - api_mode: 使用 "codex_responses" 专用 API 模式
# - env_vars: 空元组（使用外部 OAuth，无需 API Key）
# - base_url: ChatGPT 后端 API 端点
# - auth_type: 使用外部 OAuth 认证方式
openai_codex = ProviderProfile(
    name="openai-codex",
    aliases=("codex", "openai_codex"),
    api_mode="codex_responses",
    env_vars=(),  # OAuth external — no API key
    base_url="https://chatgpt.com/backend-api/codex",
    auth_type="oauth_external",
)

register_provider(openai_codex)
