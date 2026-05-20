"""AWS Bedrock 提供商配置文件。

AWS Bedrock 是亚马逊的托管 AI 服务，提供多种基础模型的统一访问接口。

本模块实现的主要特点：
- 使用 AWS SDK 进行认证和调用，而不是标准的 API Key
- API 模式为 bedrock_converse，使用 Bedrock 的 Converse API
- 没有标准的 REST /v1/models 端点，模型列表需要通过 AWS SDK 获取
- 支持通过标准 AWS 凭证链进行认证（环境变量、~/.aws/credentials、IAM 角色等）
- 提供多个别名以方便使用
"""

from providers import register_provider
from providers.base import ProviderProfile


class BedrockProfile(ProviderProfile):
    """AWS Bedrock 配置文件——无 REST /v1/models 端点；使用 AWS SDK。

    Bedrock 与其他提供商不同：
    - 不使用标准的 API Key 认证，而是使用 AWS 凭证
    - 不提供标准的 /v1/models REST 端点
    - 需要通过 AWS SDK（boto3）来列出可用模型
    - 使用专用的 bedrock_converse API 模式
    """

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """获取 Bedrock 可用模型列表。

        Bedrock 的模型列表需要使用 AWS SDK，而不是 REST 调用。
        此方法返回 None，因为：
        1. 模型列表需要 boto3 依赖和 AWS 凭证
        2. 需要处理区域特定的端点
        3. 调用者应该回退到静态模型列表或使用专用的 AWS SDK 代码

        参数:
            api_key: 未使用，Bedrock 使用 AWS 凭证
            timeout: 未使用

        返回:
            始终返回 None，调用者应使用回退机制
        """
        return None


# AWS Bedrock 提供商配置实例
#
# 字段说明:
# - name: 规范名称 "bedrock"
# - aliases: 多个别名 "aws"、"aws-bedrock"、"amazon-bedrock"、"amazon"
# - api_mode: 使用 "bedrock_converse" 模式
# - env_vars: 空元组（使用 AWS SDK 凭证，不是环境变量）
# - base_url: Bedrock 运行时端点（默认为 us-east-1 区域）
# - auth_type: 使用 AWS SDK 认证方式
bedrock = BedrockProfile(
    name="bedrock",
    aliases=("aws", "aws-bedrock", "amazon-bedrock", "amazon"),
    api_mode="bedrock_converse",
    env_vars=(),  # AWS SDK credentials — not env vars
    base_url="https://bedrock-runtime.us-east-1.amazonaws.com",
    auth_type="aws_sdk",
)

register_provider(bedrock)
