# Hermes Agent 开发者指南

本指南面向希望为 Hermes Agent 做贡献或扩展其功能的开发者。

## 目录

- [开发环境搭建](#开发环境搭建)
- [项目结构](#项目结构)
- [代码规范](#代码规范)
- [测试指南](#测试指南)
- [贡献流程](#贡献流程)
- [创建技能](#创建技能)
- [创建工具](#创建工具)
- [创建平台集成](#创建平台集成)
- [调试技巧](#调试技巧)
- [性能优化](#性能优化)

## 开发环境搭建

### 前置要求

- Python 3.11+
- Node.js 18+（用于前端和工具）
- Git
- Docker（可选，用于容器化测试）
- uv（Python 包管理器）

### 克隆仓库

```bash
# 克隆主仓库
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent

# 如果你计划贡献，请先 fork，然后：
git clone https://github.com/YOUR_USERNAME/hermes-agent.git
cd hermes-agent
git remote add upstream https://github.com/NousResearch/hermes-agent.git
```

### 安装开发依赖

```bash
# 方式一：使用提供的设置脚本
./setup-hermes.sh

# 方式二：手动设置
# 1. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 创建虚拟环境
uv venv venv --python 3.11
source venv/bin/activate

# 3. 安装所有依赖（包括开发依赖）
uv pip install -e ".[all,dev]"

# 4. 安装 Node.js 依赖（用于前端）
npm install
cd web && npm install && cd ..
cd ui-tui && npm install && cd ..
```

### 验证安装

```bash
# 运行测试
python -m pytest tests/ -v

# 运行 CLI
./hermes --help

# 代码检查
ruff check .
```

### 配置开发环境

```bash
# 创建开发配置目录
mkdir -p ~/.hermes-dev

# 复制示例配置
cp .env.example ~/.hermes-dev/.env
cp cli-config.yaml.example ~/.hermes-dev/config.yaml

# 设置 HERMES_HOME 环境变量（可选，用于开发）
export HERMES_HOME=~/.hermes-dev
```

### Git 工作流设置

```bash
# 设置 user.name 和 user.email
git config user.name "Your Name"
git config user.email "your.email@example.com"

# 为 PR 做准备
git checkout -b feature/your-feature-name main
```

## 项目结构

### 目录结构概览

```
hermes-agent/
├── agent/                    # 代理核心逻辑
├── acp_adapter/             # Agent Client Protocol 适配器
├── acp_registry/            # ACP 注册表
├── cron/                    # 定时任务相关
├── docker/                  # Docker 相关文件
├── docs/                    # 文档
├── gateway/                 # 消息网关
│   ├── platforms/          # 平台集成
│   │   ├── telegram.py
│   │   ├── discord.py
│   │   └── ...
│   └── delivery.py         # 消息投递
├── hermes_cli/             # CLI 主模块
│   ├── __main__.py        # 入口点
│   ├── tools_config.py    # 工具配置
│   └── web_dist/          # 构建的 Web UI
├── locales/                # 本地化文件
├── optional-skills/        # 可选技能集合
│   ├── autonomous-ai-agents/
│   ├── blockchain/
│   ├── communication/
│   └── ...
├── plugins/                # 插件系统
├── providers/              # LLM 提供商实现
├── scripts/                # 辅助脚本
├── skills/                 # 内置技能
├── tests/                  # 测试
│   ├── unit/              # 单元测试
│   ├── integration/       # 集成测试
│   └── fixtures/          # 测试固件
├── tools/                  # 工具实现
│   ├── terminal.py
│   ├── web.py
│   ├── file.py
│   └── ...
├── ui-tui/                 # 终端 UI（React Ink）
├── web/                    # Web 仪表盘 UI
└── website/                # 项目网站
```

### 核心模块说明

| 模块 | 说明 |
|------|------|
| `agent/` | 代理核心循环、思维链、工具调用协调 |
| `gateway/` | 消息平台集成，处理多平台消息收发 |
| `hermes_cli/` | CLI 主程序，包含命令解析、配置管理 |
| `tools/` | 内置工具实现（终端、文件、Web 等） |
| `providers/` | LLM 提供商抽象和实现 |
| `skills/` | 技能系统，技能的加载和执行 |

### 关键数据结构

```python
# hermes_state.py - 会话状态管理
class ConversationState:
    """会话状态"""
    messages: List[Message]
    tools: List[Tool]
    memory: Memory

# trajectory_compressor.py - 对话轨迹
class Trajectory:
    """对话轨迹，用于压缩和回放"""
    turns: List[Turn]
    
    def compress(self) -> 'Trajectory':
        """压缩轨迹"""
```

## 代码规范

### Python 代码规范

项目使用以下工具进行代码质量管理：

| 工具 | 用途 | 配置文件 |
|------|------|----------|
| `ruff` | 代码 lint 和格式化 | `pyproject.toml` |
| `mypy` 或 `pyright` | 类型检查 | `pyproject.toml` |
| `pytest` | 测试框架 | `pyproject.toml` |

### 代码检查和格式化

```bash
# 运行代码检查
ruff check .

# 自动修复可以修复的问题
ruff check . --fix

# 格式化代码
ruff format .

# 类型检查（如果配置了）
pyright
```

### 代码风格指南

1. **类型注解**：所有公共 API 必须有类型注解

```python
from typing import List, Optional, Dict, Any

def process_messages(messages: List[Dict[str, Any]]) -> Optional[str]:
    """处理消息并返回结果"""
    # 实现
```

2. **文档字符串**：使用 Google 风格的 docstring

```python
def create_skill(name: str, description: str, content: str) -> Skill:
    """创建一个新技能。
    
    Args:
        name: 技能名称
        description: 技能描述
        content: 技能内容
    
    Returns:
        创建的 Skill 对象
    
    Raises:
        ValueError: 如果技能名称无效
    """
    # 实现
```

3. **错误处理**：适当处理异常，提供有意义的错误信息

```python
try:
    result = api_call()
except APIError as e:
    logger.error(f"API 调用失败: {e}")
    raise HermesError(f"无法完成操作: {e}") from e
```

4. **日志记录**：使用 `hermes_logging` 模块

```python
from hermes_logging import get_logger

logger = get_logger(__name__)

logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告信息")
logger.error("错误信息")
```

5. **常量定义**：使用 `hermes_constants.py` 或模块级常量

```python
# hermes_constants.py
DEFAULT_MODEL = "anthropic/claude-opus-4.6"
MAX_TOOL_CALLS = 50
```

### 提交信息规范

使用清晰的提交信息格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

Type 可选值：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具链相关

示例：

```
feat(gateway): 添加 Teams 平台支持

- 实现 Teams 集成
- 添加身份验证
- 编写文档

Closes #123
```

## 测试指南

### 测试结构

```
tests/
├── unit/              # 单元测试
│   ├── test_agent.py
│   ├── test_tools.py
│   └── ...
├── integration/       # 集成测试（需要 API 密钥）
│   ├── test_gateway.py
│   └── ...
└── fixtures/          # 测试固件
    └── sample_data.py
```

### 运行测试

```bash
# 运行所有单元测试
python -m pytest tests/unit -v

# 运行特定测试文件
python -m pytest tests/unit/test_agent.py -v

# 运行特定测试函数
python -m pytest tests/unit/test_agent.py::test_agent_init -v

# 并行运行测试（使用 pytest-xdist）
python -m pytest tests/unit -n auto

# 生成覆盖率报告
python -m pytest tests/unit --cov=agent --cov-report=html

# 运行集成测试（需要 API 密钥）
python -m pytest tests/integration -v -m "integration"
```

### 编写测试

使用 pytest 编写测试：

```python
# tests/unit/test_example.py
import pytest
from my_module import my_function

def test_my_function():
    """测试 my_function 的基本行为"""
    result = my_function(1, 2)
    assert result == 3

def test_my_function_with_error():
    """测试错误情况"""
    with pytest.raises(ValueError):
        my_function(-1, 2)

@pytest.fixture
def sample_data():
    """测试固件示例"""
    return {"key": "value"}

def test_with_fixture(sample_data):
    """使用固件的测试"""
    assert sample_data["key"] == "value"
```

### 使用 Mock

```python
from unittest.mock import Mock, patch

@patch("module.external_api")
def test_with_mock(mock_api):
    """使用 mock 的测试"""
    mock_api.return_value = {"result": "success"}
    
    result = my_function()
    
    mock_api.assert_called_once()
    assert result == {"result": "success"}
```

## 贡献流程

### 分支管理策略

- `main`: 主分支，保持稳定
- `feature/*`: 新功能开发
- `fix/*`: Bug 修复
- `docs/*`: 文档更新

### 标准贡献流程

1. **同步最新代码**

```bash
git checkout main
git pull upstream main
```

2. **创建功能分支**

```bash
git checkout -b feature/your-feature-name
```

3. **开发和提交**

```bash
# 进行代码修改
git add .
git commit -m "feat: 描述你的更改"
```

4. **运行测试和检查**

```bash
python -m pytest tests/unit -v
ruff check .
ruff format .
```

5. **推送分支**

```bash
git push origin feature/your-feature-name
```

6. **创建 Pull Request**

在 GitHub 上创建 PR，填写 PR 模板：

```markdown
## 描述
简要描述你的更改

## 类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 文档更新
- [ ] 重构

## 测试
- [ ] 已添加单元测试
- [ ] 已运行现有测试

## 相关 Issue
Closes #issue-number
```

### PR 审核流程

1. 自动化检查（CI）通过
2. 至少一名维护者审核
3. 解决审核意见
4. Squash 并合并到 main

## 创建技能

### 技能文件结构

技能是 Hermes Agent 从经验中学习并重用的关键方式。技能文件通常存储在 `~/.hermes/skills/` 或项目的 `skills/` 目录中。

```
skills/
├── my-skill.md
└── another-skill.md
```

### 技能文件格式

```markdown
# 技能名称

## 描述
简要描述这个技能的用途

## 使用场景
- 场景 1
- 场景 2

## 步骤
1. 步骤 1
2. 步骤 2
3. 步骤 3

## 示例
示例用法

## 注意事项
- 注意点 1
- 注意点 2
```

### 注册技能

在代码中注册自定义技能：

```python
from skills import SkillRegistry, Skill

# 创建技能
skill = Skill(
    name="my-custom-skill",
    description="我的自定义技能",
    content="技能内容..."
)

# 注册技能
registry = SkillRegistry()
registry.register(skill)
```

## 创建工具

### 工具基类

所有工具继承自基类：

```python
from typing import Any, Dict, List
from tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    """我的自定义工具"""
    
    name = "my_tool"
    description = "工具描述"
    
    async def __call__(self, param1: str, param2: int = 10) -> ToolResult:
        """执行工具
        
        Args:
            param1: 参数 1
            param2: 参数 2
            
        Returns:
            工具执行结果
        """
        # 实现工具逻辑
        try:
            result = await self._do_something(param1, param2)
            return ToolResult(success=True, output=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _do_something(self, param1: str, param2: int) -> str:
        """实际执行逻辑"""
        return f"处理了 {param1}, {param2}"
```

### 注册工具

在 `toolsets.py` 中注册工具：

```python
# toolsets.py
from .my_tool import MyTool

TOOLSETS = {
    "my_toolset": [MyTool],
    # 其他工具集...
}
```

### 在配置中启用

```yaml
# ~/.hermes/config.yaml
platform_toolsets:
  cli: ["hermes-cli", "my_toolset"]
```

## 创建平台集成

### 平台接口

在 `gateway/platforms/` 中创建新平台：

```python
# gateway/platforms/my_platform.py
from typing import AsyncIterator, Optional
from gateway.platforms.base import Platform, Message

class MyPlatform(Platform):
    """我的平台集成"""
    
    name = "my_platform"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key")
    
    async def start(self):
        """启动平台"""
        # 初始化连接
    
    async def stop(self):
        """停止平台"""
        # 清理资源
    
    async def receive_messages(self) -> AsyncIterator[Message]:
        """接收消息"""
        while True:
            # 获取消息
            msg = await self._get_next_message()
            yield msg
    
    async def send_message(self, message: Message):
        """发送消息"""
        # 发送消息逻辑
    
    async def _get_next_message(self) -> Optional[Message]:
        """获取下一条消息"""
        # 实现
```

### 注册平台

在 `gateway/platforms/__init__.py` 中注册：

```python
from .my_platform import MyPlatform

PLATFORMS = {
    "my_platform": MyPlatform,
    # 其他平台...
}
```

## 调试技巧

### 启用详细日志

```yaml
# ~/.hermes/config.yaml
agent:
  verbose: true

display:
  tool_progress: "verbose"
```

或使用命令行参数：

```bash
HERMES_LOG_LEVEL=DEBUG ./hermes
```

### 使用调试器

```python
# 在代码中插入断点
import debugpy

# 等待调试器附加
debugpy.listen(5678)
print("等待调试器附加...")
debugpy.wait_for_client()
debugpy.breakpoint()  # 断点处
```

### 使用开发模式运行

```python
# 使用测试配置运行
import os
os.environ["HERMES_HOME"] = "/path/to/test/config"

from hermes_cli.main import main
main()
```

### 检查状态

```python
# 打印当前状态
from hermes_state import get_state
state = get_state()
print(state)
```

## 性能优化

### 性能分析

```python
import cProfile
import pstats

def profile_agent():
    """分析代理性能"""
    profiler = cProfile.Profile()
    profiler.enable()
    
    # 运行代码
    main()
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    stats.print_stats(20)
```

### 常见优化点

1. **减少 API 调用**：缓存常用结果
2. **上下文压缩**：合理配置压缩参数
3. **工具批处理**：合并多个工具调用
4. **异步 I/O**：确保所有 I/O 都是异步的

```python
# 异步 I/O 示例
import asyncio

async def process_multiple(items: List[Any]) -> List[Any]:
    """并行处理多个项目"""
    tasks = [process_item(item) for item in items]
    return await asyncio.gather(*tasks)

async def process_item(item: Any) -> Any:
    """处理单个项目"""
    # 异步处理
```

## 发布流程

对于维护者，发布新版本的流程：

1. **更新版本号**

```python
# hermes_constants.py
__version__ = "0.14.0"
```

2. **创建发布说明**

```bash
# 创建 RELEASE_v0.14.0.md
# 包含更改内容、新功能、修复
```

3. **创建 Git 标签**

```bash
git tag -a v0.14.0 -m "Release v0.14.0"
git push origin v0.14.0
```

4. **发布到 PyPI（如果适用）**

```bash
# 构建包
python -m build

# 上传
twine upload dist/*
```

## 资源链接

- [项目 README](../README.zh-CN.md)
- [贡献指南](../CONTRIBUTING.md)
- [问题追踪](https://github.com/NousResearch/hermes-agent/issues)
- [Discord 社区](https://discord.gg/NousResearch)

## 获取帮助

如果在开发过程中遇到问题：

1. 查看文档
2. 搜索现有 Issue
3. 在 Discord 提问
4. 创建新 Issue（如果是 Bug 或功能请求）
