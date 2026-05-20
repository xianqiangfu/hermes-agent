"""DeepSeek 提供商配置文件。

DeepSeek 的 V4 系列（以及旧版 ``deepseek-reasoner``）在未设置
``extra_body.thinking`` 时默认开启思考模式。API 会返回
``reasoning_content`` 并开始强制要求后续回合回显该内容；
结合 Hermes 重播历史的方式，这会导致在第一次工具调用后出现
臭名昭著的 HTTP 400 ``reasoning_content must be passed back`` 错误
（#15700、#17212、#17825）。

本配置文件覆盖 :meth:`build_api_kwargs_extras` 以镜像 DeepSeek 的
OpenAI 兼容端点期望的 Kimi / Moonshot 有线格式：

    {"reasoning_effort": "<low|medium|high|max>",
     "extra_body": {"thinking": {"type": "enabled" | "disabled"}}}

非思考模型（目前只有 ``deepseek-chat``，即 V3）保持不变，
以免干扰 V3 的有线格式。

主要功能：
- 自动检测支持思考模式的模型（V4+、deepseek-reasoner）
- 显式设置 thinking 类型以避免 reasoning_content 回显陷阱
- 正确映射推理努力级别（low/medium/high/max）
- 对 V3 模型保持向后兼容
"""

from __future__ import annotations

from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


def _model_supports_thinking(model: str | None) -> bool:
    """检测 DeepSeek 模型是否支持思考模式。

    目前覆盖的模型系列：
    - V4 系列（``deepseek-v4-pro``、``deepseek-v4-flash`` 以及任何未来的
      ``deepseek-v4-*`` 变体）
    - 旧版 ``deepseek-reasoner``（R1）

    排除的模型：
    - ``deepseek-chat``（V3，无思考模式）
    - 其他未知模型

    参数:
        model: 模型名称字符串

    返回:
        如果模型支持思考模式则返回 True，否则返回 False
    """
    m = (model or "").strip().lower()
    if not m:
        return False
    if m.startswith("deepseek-v") and not m.startswith("deepseek-v3"):
        # deepseek-v4-*, deepseek-v5-*, 等 —— V4+ 的每个版本都有
        # 思考模式。v3 明确排除。
        return True
    if m == "deepseek-reasoner":
        return True
    return False


class DeepSeekProfile(ProviderProfile):
    """DeepSeek 配置文件——处理 extra_body.thinking + 顶级 reasoning_effort。

    DeepSeek 需要特殊的有线格式来避免 reasoning_content 回显问题：
    1. 必须显式设置 extra_body.thinking.type 为 "enabled" 或 "disabled"
    2. 可选地在顶级设置 reasoning_effort 控制推理强度
    """

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict | None = None, model: str | None = None, **context
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """构建 DeepSeek 特定的 API 参数。

        此方法执行以下操作：
        1. 检测模型是否支持思考模式
        2. 如果支持，显式设置 thinking 类型以避免回显陷阱
        3. 如果启用，映射推理努力级别到 DeepSeek 期望的格式
        4. 如果不支持或禁用，返回适当的配置

        参数:
            reasoning_config: 推理配置字典，可能包含 enabled 和 effort 字段
            model: 模型名称，用于检测是否支持思考模式
            **context: 其他上下文参数

        返回:
            元组 (extra_body_additions, top_level_kwargs)
        """
        extra_body: dict[str, Any] = {}
        top_level: dict[str, Any] = {}

        if not _model_supports_thinking(model):
            # V3 / 未知模型——保持有线格式不变，维持当前行为。
            return extra_body, top_level

        # 确定启用/禁用状态。默认启用以匹配 DeepSeek 的 API 默认值；
        # API 要求显式设置此值以避免后续回合的 reasoning_content 回显陷阱。
        enabled = True
        if isinstance(reasoning_config, dict) and reasoning_config.get("enabled") is False:
            enabled = False

        extra_body["thinking"] = {"type": "enabled" if enabled else "disabled"}

        if not enabled:
            return extra_body, top_level

        # 努力级别映射。直接传递 low/medium/high；xhigh/max → max。
        # 当未设置努力级别时，我们省略 reasoning_effort，以便 DeepSeek
        # 应用其服务器默认值（当前为 high）。
        if isinstance(reasoning_config, dict):
            effort = (reasoning_config.get("effort") or "").strip().lower()
            if effort in {"xhigh", "max"}:
                top_level["reasoning_effort"] = "max"
            elif effort in {"low", "medium", "high"}:
                top_level["reasoning_effort"] = effort

        return extra_body, top_level


# DeepSeek 提供商配置实例
#
# 字段说明:
# - name: 规范名称 "deepseek"
# - aliases: 别名 "deepseek-chat"
# - env_vars: 使用 DEEPSEEK_API_KEY 环境变量
# - display_name: 显示名称 "DeepSeek"
# - description: 描述信息
# - signup_url: 获取 API Key 的链接
# - fallback_models: 精选模型列表，当实时获取失败时使用
# - base_url: DeepSeek API 基础 URL
# - default_aux_model: 使用 deepseek-chat 作为辅助任务的廉价模型
deepseek = DeepSeekProfile(
    name="deepseek",
    aliases=("deepseek-chat",),
    env_vars=("DEEPSEEK_API_KEY",),
    display_name="DeepSeek",
    description="DeepSeek — native DeepSeek API",
    signup_url="https://platform.deepseek.com/",
    fallback_models=(
        "deepseek-chat",
        "deepseek-reasoner",
    ),
    base_url="https://api.deepseek.com/v1",
    default_aux_model="deepseek-chat",
)

register_provider(deepseek)
