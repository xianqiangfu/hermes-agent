# 工具系统文档

## 概述

Hermes Agent 的工具系统是一个灵活、可扩展的模块化架构，支持通过工具（Tools）与大语言模型进行交互。工具系统采用注册表模式，支持内置工具、MCP 服务器工具和插件工具的统一管理。

## 核心架构

### 1. 工具注册表 (`tools/registry.py`)

工具注册表是整个工具系统的核心，负责：
- 工具元数据存储
- 工具可用性检查
- 工具调度执行
- 工具集管理

#### 核心类

**`ToolEntry`** - 工具元数据容器
```python
class ToolEntry:
    name: str                    # 工具名称
    toolset: str                 # 所属工具集
    schema: dict                 # OpenAI 格式的工具 schema
    handler: Callable            # 工具处理函数
    check_fn: Callable           # 可用性检查函数
    requires_env: list           # 所需环境变量
    is_async: bool               # 是否为异步处理器
    description: str             # 工具描述
    emoji: str                   # 工具图标
    max_result_size_chars: int   # 最大结果大小
    dynamic_schema_overrides: Callable  # 动态 schema 覆盖
```

**`ToolRegistry`** - 全局单例注册表
```python
class ToolRegistry:
    # 注册工具
    register(name, toolset, schema, handler, ...)

    # 注销工具
    deregister(name)

    # 获取工具定义
    get_definitions(tool_names)

    # 调度执行工具
    dispatch(name, args, **kwargs)

    # 工具集管理
    register_toolset_alias(alias, toolset)
    get_tool_names_for_toolset(toolset)
```

#### 工具可用性检查

工具系统使用 TTL 缓存机制（默认 30 秒）缓存 `check_fn` 结果，避免频繁探测外部状态：
```python
_check_fn_cache: Dict[Callable, tuple[float, bool]]
_CHECK_FN_TTL_SECONDS = 30.0
```

### 2. 工具定义和发现

#### 内置工具发现

`discover_builtin_tools()` 函数通过 AST 分析自动发现 `tools/` 目录下的工具模块：
```python
def _module_registers_tools(module_path: Path) -> bool:
    """检查模块是否包含顶级 registry.register() 调用"""
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module_path))
    return any(_is_registry_register_call(stmt) for stmt in tree.body)
```

#### 工具注册

每个工具模块在导入时通过 `registry.register()` 注册：
```python
from tools.registry import registry, tool_error, tool_result

def terminal_handler(args: dict) -> str:
    # 工具实现
    return tool_result({"output": "command output"})

registry.register(
    name="terminal",
    toolset="terminal",
    schema={
        "type": "function",
        "name": "terminal",
        "description": "Execute a terminal command",
        "parameters": {
            "type": "object",
            "properties": {...},
            "required": ["command"]
        }
    },
    handler=terminal_handler,
    check_fn=check_terminal_requirements,  # 可选
    requires_env=[],                        # 可选
    is_async=False,
)
```

### 3. 工具调度系统 (`model_tools.py`)

#### 工具定义获取

`get_tool_definitions()` 是模型获取可用工具的主入口：
```python
def get_tool_definitions(
    enabled_toolsets: List[str] = None,
    disabled_toolsets: List[str] = None,
    quiet_mode: bool = False,
) -> List[Dict[str, Any]]:
    """
    返回 OpenAI 格式的工具定义列表

    功能：
    1. 根据 enabled_toolsets/disabled_toolsets 过滤工具
    2. 运行工具的 check_fn 确定可用性
    3. 应用动态 schema 覆盖（execute_code, discord 等）
    4. 缓存结果（基于 registry._generation + config mtime）
    """
```

#### 函数调用处理

`handle_function_call()` 是工具执行的主入口：
```python
def handle_function_call(
    function_name: str,
    function_args: Dict[str, Any],
    task_id: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_task: Optional[str] = None,
    enabled_tools: Optional[List[str]] = None,
    skip_pre_tool_call_hook: bool = False,
) -> str:
    """
    执行工具并返回 JSON 格式的结果

    执行流程：
    1. 参数类型强制转换
    2. 插件 pre_tool_call 钩子
    3. ACP 编辑审批检查
    4. 工具调度执行
    5. 插件 post_tool_call 钩子
    6. 插件 transform_tool_result 钩子
    """
```

#### 参数类型强制转换

自动处理 LLM 输出的类型不匹配：
```python
def coerce_tool_args(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    将工具调用参数强制转换为 JSON Schema 声明的类型

    处理场景：
    - "42" → 42（字符串转整数）
    - "true" → True（字符串转布尔值）
    - {"urls": "https://a.com"} → {"urls": ["https://a.com"]}
    - JSON 字符串 → 解析后的对象/数组
    """
```

#### 异步桥接

`_run_async()` 提供同步到异步的无缝桥接：
```python
def _run_async(coro):
    """
    从同步上下文运行异步协程

    场景处理：
    1. 已有运行中的事件循环 → 在新线程中运行
    2. 工作线程（如 delegate_task）→ 使用线程本地循环
    3. 主线程 → 使用持久化事件循环
    """
```

### 4. 工具集系统 (`toolsets.py`)

工具集允许将工具分组，支持组合和继承：

#### 预定义工具集

```python
TOOLSETS = {
    "web": {
        "description": "Web research and content extraction tools",
        "tools": ["web_search", "web_extract"],
        "includes": []
    },
    "terminal": {
        "description": "Terminal/command execution tools",
        "tools": ["terminal", "process"],
        "includes": []
    },
    "debugging": {
        "description": "Debugging toolkit",
        "tools": ["terminal", "process"],
        "includes": ["web", "file"]  # 组合其他工具集
    },
    "hermes-cli": {
        "description": "Full interactive CLI toolset",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },
}
```

#### 工具集解析

```python
def resolve_toolset(name: str, visited: Set[str] = None) -> List[str]:
    """
    递归解析工具集，返回所有工具名称列表

    处理：
    1. 直接包含的工具
    2. 递归解析 includes 中的工具集
    3. 循环引用检测
    """
```

### 5. 环境系统 (`tools/environments/`)

终端工具支持多种执行环境：

#### 环境类型

- **local** - 本机直接执行（默认，最快）
- **docker** - Docker 容器隔离执行
- **modal** - Modal 云沙盒执行
- **vercel_sandbox** - Vercel Sandbox 云沙盒
- **ssh** - SSH 远程主机执行
- **singularity** - Singularity 容器执行
- **daytona** - Daytona 云开发环境

#### 环境基类 (`base.py`)

```python
class TerminalEnvironment:
    def execute(self, command: str, timeout: int) -> ExecutionResult:
        """执行命令并返回结果"""

    def is_available(self) -> bool:
        """检查环境是否可用"""

    def cleanup(self) -> None:
        """清理资源"""
```

### 6. 安全机制 (`tools/approval.py`)

#### 危险命令检测

```python
DANGEROUS_PATTERNS = [
    r"(?:^|\s)(?:rm\s+(?:-rf?|--recursive)?\s*/)(?![a-z])",
    r"(?:^|\s)(?:dd\s+if=/dev/zero)",
    r"(?:^|\s)(?:mkfs\.|format)",
    # ... 更多模式
]

def detect_dangerous_command(command: str) -> Optional[str]:
    """检测命令是否包含危险操作"""
```

#### 审批流程

```python
def require_approval(command: str, session_key: str = "default") -> bool:
    """
    检查命令是否需要用户审批

    流程：
    1. 检测是否为危险命令
    2. 检查永久允许列表
    3. 检查会话级已批准列表
    4. 如需审批，提示用户确认
    """
```

## 执行流程

### 工具注册流程

```
1. 工具模块导入 (tools/xxx_tool.py)
   ↓
2. 模块级调用 registry.register()
   ↓
3. ToolEntry 创建并存储到 registry._tools
   ↓
4. 工具集关联检查函数存储到 registry._toolset_checks
```

### 工具发现流程

```
1. discover_builtin_tools() 扫描 tools/ 目录
   ↓
2. AST 分析检测 registry.register() 调用
   ↓
3. importlib.import_module() 导入模块
   ↓
4. 模块级注册代码执行
   ↓
5. 工具注册到注册表
```

### 工具调用流程

```
1. 模型请求工具调用 (function_name, function_args)
   ↓
2. handle_function_call()
   ↓
3. coerce_tool_args() 参数类型转换
   ↓
4. 插件 pre_tool_call 钩子（可能阻止执行）
   ↓
5. ACP 编辑审批检查
   ↓
6. registry.dispatch() 调度执行
   ↓
7. 工具 handler 执行
   ↓
8. 插件 post_tool_call 钩子
   ↓
9. 插件 transform_tool_result 钩子
   ↓
10. 返回 JSON 格式结果
```

### 工具定义获取流程

```
1. get_tool_definitions(enabled_toolsets)
   ↓
2. resolve_toolset() 解析工具集
   ↓
3. 构建工具名称集合
   ↓
4. 应用 disabled_toolsets 排除
   ↓
5. registry.get_definitions() 过滤可用工具
   ↓
6. 运行 check_fn 检查可用性（带 TTL 缓存）
   ↓
7. 应用动态 schema 覆盖
   ↓
8. Schema 清洗（兼容性）
   ↓
9. 返回 OpenAI 格式工具定义列表
```

## 扩展指南

### 创建新工具

1. 在 `tools/` 目录创建新的工具文件（如 `my_tool.py`）
2. 定义工具处理函数
3. 调用 `registry.register()` 注册
4. 在 `toolsets.py` 中添加到相应工具集

```python
# tools/my_tool.py
from tools.registry import registry, tool_error, tool_result

def my_tool_handler(args: dict) -> str:
    """工具处理函数"""
    param = args.get("param")
    try:
        # 工具实现逻辑
        result = process_param(param)
        return tool_result({"success": True, "data": result})
    except Exception as e:
        return tool_error(f"处理失败: {e}")

# 注册工具
registry.register(
    name="my_tool",
    toolset="my_toolset",
    schema={
        "type": "function",
        "name": "my_tool",
        "description": "我的工具描述",
        "parameters": {
            "type": "object",
            "properties": {
                "param": {
                    "type": "string",
                    "description": "参数描述"
                }
            },
            "required": ["param"]
        }
    },
    handler=my_tool_handler,
    check_fn=lambda: True,  # 可选：可用性检查
)
```

### 创建异步工具

```python
import asyncio

async def async_tool_handler(args: dict) -> str:
    """异步工具处理函数"""
    result = await async_operation()
    return tool_result(result)

registry.register(
    name="async_tool",
    toolset="async_tools",
    schema={...},
    handler=async_tool_handler,
    is_async=True,  # 标记为异步
)
```

### 添加工具可用性检查

```python
def check_my_tool_requirements() -> bool:
    """检查工具运行依赖是否满足"""
    try:
        import some_dependency
        # 检查外部条件
        return True
    except ImportError:
        return False

registry.register(
    name="my_tool",
    toolset="my_toolset",
    schema={...},
    handler=my_tool_handler,
    check_fn=check_my_tool_requirements,
    requires_env=["MY_API_KEY"],
)
```

### 动态 Schema 覆盖

当工具 schema 需要根据运行时配置动态调整时：

```python
def get_dynamic_schema_overrides():
    """返回动态 schema 覆盖"""
    from hermes_cli.config import load_config
    cfg = load_config()
    max_items = cfg.get("my_tool_max_items", 10)
    return {
        "description": f"工具描述（最多处理 {max_items} 项）",
        "parameters": {
            "properties": {
                "max_items": {
                    "type": "integer",
                    "default": max_items
                }
            }
        }
    }

registry.register(
    name="dynamic_tool",
    toolset="dynamic",
    schema={...},
    handler=handler,
    dynamic_schema_overrides=get_dynamic_schema_overrides,
)
```

### 创建自定义工具集

在 `toolsets.py` 中添加：

```python
TOOLSETS = {
    # ... 现有工具集
    "my_toolset": {
        "description": "我的自定义工具集",
        "tools": ["my_tool", "another_tool"],
        "includes": ["web"]  # 组合现有工具集
    },
}
```

## 辅助函数

### 工具结果返回

```python
from tools.registry import tool_error, tool_result

# 成功结果
return tool_result({"success": True, "data": "value"})

# 错误结果
return tool_error("操作失败")

# 带额外字段的错误
return tool_error("文件未找到", code=404)
```

### 工具调用策略

工具系统支持两种调用策略：

1. **顺序调用** - 默认行为，工具按顺序执行
2. **并发调用** - `delegate_task` 支持并发执行多个工具

## 常见工具类别

### 文件操作工具
- `read_file` - 读取文件内容
- `write_file` - 写入文件
- `patch` - 使用 diff/patch 修改文件
- `search_files` - 搜索文件内容

### 终端工具
- `terminal` - 执行命令
- `process` - 进程管理

### Web 工具
- `web_search` - 网络搜索
- `web_extract` - 网页内容提取
- `browser_*` - 浏览器自动化（导航、点击、输入等）

### 视觉工具
- `vision_analyze` - 图像分析
- `image_generate` - 图像生成
- `video_analyze` - 视频分析
- `video_generate` - 视频生成

### 代码执行
- `execute_code` - 在沙盒中执行 Python 代码

### 技能系统
- `skills_list` - 列出可用技能
- `skill_view` - 查看技能内容
- `skill_manage` - 管理技能

### 消息平台
- `send_message` - 跨平台消息发送
- `discord` - Discord 机器人
- `feishu_*` - 飞书集成

### 智能家居
- `ha_*` - Home Assistant 集成

## 最佳实践

1. **工具命名** - 使用清晰、描述性的名称（如 `read_file` 而非 `rf`）
2. **错误处理** - 所有工具都应该捕获异常并通过 `tool_error()` 返回
3. **参数验证** - 在处理函数中验证参数
4. **结果格式** - 返回结构化的 JSON 数据，便于模型理解
5. **可用性检查** - 为需要外部依赖的工具提供 `check_fn`
6. **文档化** - 在 schema 的 `description` 中提供清晰的说明
7. **安全性** - 对于危险操作使用审批系统
8. **异步支持** - 对于 I/O 密集型操作使用异步处理器

## 性能优化

1. **缓存** - 工具定义和可用性检查使用缓存
2. **惰性导入** - 避免在模块顶层导入重型依赖
3. **批量操作** - 尽量支持批量参数减少调用次数
4. **结果大小限制** - 设置 `max_result_size_chars` 避免返回过多数据
5. **异步处理** - 使用异步工具提高并发性能

## 相关文件

- `tools/registry.py` - 工具注册表核心实现
- `model_tools.py` - 工具调度和编排层
- `toolsets.py` - 工具集定义和解析
- `tools/approval.py` - 危险命令审批系统
- `tools/file_tools.py` - 文件操作工具实现
- `tools/terminal_tool.py` - 终端工具实现
- `tools/browser_tool.py` - 浏览器自动化工具
- `tools/environments/` - 各种执行环境实现

## 参考资料

- OpenAI Function Calling: https://platform.openai.com/docs/guides/function-calling
- JSON Schema: https://json-schema.org/