# Hermes Agent 核心代理引擎

## 概述

Hermes Agent 的核心代理引擎是一个基于工具调用（Tool-Calling）的 AI 代理系统，支持多轮对话、并发工具执行、上下文压缩和跨平台适配。该引擎设计为模块化、可扩展的架构，支持多种 LLM 提供商（Anthropic、OpenAI、Bedrock、OpenRouter 等）。

## 架构设计

### 核心组件

```
agent/
├── __init__.py                 # 模块入口
├── agent_init.py               # 代理初始化逻辑
├── conversation_loop.py        # 对话循环（核心引擎）
├── tool_executor.py            # 工具执行器（并发/顺序）
├── context_engine.py           # 上下文引擎抽象接口
├── context_compressor.py      # 内置上下文压缩器
├── prompt_builder.py          # 系统提示词构建器
├── system_prompt.py           # 系统提示词组装
├── iteration_budget.py        # 迭代预算管理
├── transports/                # 传输层（API适配器）
│   ├── base.py               # 传输层基类
│   ├── anthropic.py          # Anthropic API 适配
│   ├── chat_completions.py   # OpenAI 兼容 API 适配
│   ├── bedrock.py            # AWS Bedrock 适配
│   ├── codex.py              # OpenAI Codex API 适配
│   └── codex_app_server.py   # Codex 应用服务器适配
├── anthropic_adapter.py       # Anthropic SDK 适配器
├── auxiliary_client.py       # 辅助客户端（OpenRouter 等）
├── memory_manager.py          # 记忆管理器
└── model_metadata.py         # 模型元数据管理
```

### 核心类

| 类名 | 文件 | 作用 |
|------|------|------|
| `AIAgent` | `run_agent.py` | 代理主类，封装整个对话流程 |
| `ContextEngine` | `context_engine.py` | 上下文引擎抽象基类 |
| `ContextCompressor` | `context_compressor.py` | 内置上下文压缩实现 |
| `IterationBudget` | `iteration_budget.py` | 迭代预算计数器（线程安全） |

## 核心流程

### 1. 代理初始化

**入口**: `agent_init.py` → `init_agent(agent, ...)`

初始化流程：

1. **配置加载**：加载模型配置、工具集设置、压缩参数
2. **提供商检测**：自动识别提供商（Anthropic、OpenAI、Bedrock 等）
3. **API 模式选择**：根据提供商选择合适的 API 模式
   - `anthropic_messages` - Anthropic 原生 API
   - `chat_completions` - OpenAI 兼容 API
   - `bedrock_converse` - AWS Bedrock Converse API
   - `codex_responses` - OpenAI Codex Responses API
   - `codex_app_server` - Codex 应用服务器模式
4. **客户端构建**：初始化对应提供商的 API 客户端
5. **工具加载**：获取并过滤可用工具
6. **上下文引擎初始化**：加载并初始化上下文管理器
7. **记忆系统初始化**：加载内置记忆和外部记忆提供程序

**关键状态**：
- `agent.model`: 当前使用的模型
- `agent.provider`: 提供商标识
- `agent.api_mode`: API 模式
- `agent.tools`: 可用工具列表
- `agent.context_compressor`: 上下文压缩器实例
- `agent.iteration_budget`: 迭代预算（默认 90 次迭代）

### 2. 对话循环

**入口**: `conversation_loop.py` → `run_conversation(agent, ...)`

这是代理引擎的核心循环，负责驱动一个完整的对话轮次。

#### 2.1 前置检查

```
用户消息
    ↓
代理内省/消息清理
    ↓
会话历史恢复（如有）
    ↓
前置压缩检查（如已超阈值）
    ↓
系统提示词恢复/构建（缓存）
    ↓
插件预 LLM 调用钩子（pre_llm_call）
```

#### 2.2 主循环

```
while (api_call_count < max_iterations and iteration_budget.remaining > 0) or budget_grace_call:
    ├── 中断检查（用户发送新消息）
    ├── 迭代预算消费
    ├── 步骤回调（step_callback）
    ├── /steer 机制：注入用户引导到工具结果
    │
    ├── API 消息构建
    │   ├── 清理工具调用参数
    │   ├── 修复消息序列（角色交替）
    │   ├── 注入临时上下文（记忆 + 插件）
    │   ├── 应用提示词缓存（Anthropic）
    │   └── 清理消息（代理字符、删除思维块）
    │
    ├── API 调用（重试机制）
    │   ├── 流式/非流式选择
    │   ├── 响应验证
    │   ├── 错误分类与恢复
    │   │   ├── 429 速率限制 → 指数退避
    │   │   ├── 上下文超限 → 触发压缩
    │   │   ├── 4xx 认证错误 → 凭证刷新
    │   │   ├── 5xx 服务器错误 → 重试
    │   │   └── 回退链激活 → 切换提供商
    │   └── 使用量统计与成本估算
    │
    └── 处理 API 响应
        ├── finish_reason 处理
        │   ├── stop → 正常完成
        │   ├── length → 输出截断（请求续写）
        │   └── tool_calls → 工具调用
        │
        └── 工具调用执行
            ├── 工具调用守卫（guardrails）
            ├── 并发/顺序执行选择
            │   ├── 并发：`execute_tool_calls_concurrent`
            │   └── 顺序：`execute_tool_calls_sequential`
            ├── 执行前检查点（文件变更）
            ├── 工具结果处理
            │   ├── 多模态结果处理
            │   ├── 记忆写入通知
            │   └── 子目录提示注入
            └── 工具结果添加到消息历史
```

#### 2.3 循环结束条件

- **正常完成**：模型返回文本响应且无工具调用
- **预算耗尽**：达到 `max_iterations` 限制
- **用户中断**：收到用户中断信号
- **严重错误**：所有重试和回退均失败

### 3. 工具调用流程

**入口**: `tool_executor.py`

#### 3.1 工具执行模式

**并发执行**（`execute_tool_calls_concurrent`）：
- 使用线程池（最多 8 个工作线程）
- 独立工具并发执行
- 定期心跳以防止网关超时
- 支持中途取消

**顺序执行**（`execute_tool_calls_sequential`）：
- 逐个执行工具调用
- 每个工具执行后检查中断
- 适用于交互式工具（如 `clarify`）

#### 3.2 工具执行流程

```
工具调用（名称 + 参数）
    ↓
插件预检查（get_pre_tool_call_block_message）
    ↓
工具守卫检查（ToolCallGuardrailController）
    ↓
执行前检查点（文件变更）
    ↓
工具分发
    ├── todo → 内置 Todo Store
    ├── session_search → 会话搜索
    ├── memory → 内置记忆工具
    ├── delegate_task → 子代理委托
    ├── context_engine tools → 上下文引擎工具
    ├── memory_manager tools → 外部记忆提供程序工具
    └── 其他 → handle_function_call（注册的工具）
    ↓
工具执行
    ├── 活动回调（网关超时检测）
    ├── 执行时错误处理
    └── 结果清理（多模态处理）
    ↓
执行后检查点验证
    ↓
工具结果持久化（可选）
    ↓
工具结果添加到消息历史
```

#### 3.3 内置工具

| 工具名称 | 作用 |
|---------|------|
| `todo` | 任务列表管理（临时工作跟踪） |
| `session_search` | 跨会话历史搜索 |
| `memory` | 内置持久记忆（MEMORY.md + USER.md） |
| `clarify` | 交互式用户澄清 |
| `delegate_task` | 子代理任务委托 |

### 4. 系统提示词构建

**入口**: `system_prompt.py` → `build_system_prompt_parts(agent, ...)`

系统提示词分三层构建：

#### 4.1 稳定层（Stable）

不变部分，在会话生命周期内保持一致：

1. **代理身份**：
   - 优先从 `~/.hermes/SOUL.md` 加载
   - 回退到 `DEFAULT_AGENT_IDENTITY`（Hermes Agent 默认身份）
   - 提示词注入防护扫描（检测潜在攻击模式）

2. **工具引导**：
   - 记忆工具引导（`MEMORY_GUIDANCE`）
   - 会话搜索引导（`SESSION_SEARCH_GUIDANCE`）
   - 技能管理引导（`SKILLS_GUIDANCE`）
   - Kanban 工作流引导（如激活）
   - Computer Use 引导（如激活）

3. **模型家族引导**：
   - **Google 模型**：`GOOGLE_MODEL_OPERATIONAL_GUIDANCE`（绝对路径、验证优先）
   - **OpenAI 模型**：`OPENAI_MODEL_EXECUTION_GUIDANCE`（工具持久性、验证）
   - **工具使用强制**：`TOOL_USE_ENFORCEMENT_GUIDANCE`（强制使用工具）

4. **环境提示**：
   - 主机信息（本地后端）
   - 后端探测信息（远程后端）
   - WSL 环境提示（如适用）

5. **平台提示**：
   - WhatsApp、Telegram、Discord、Slack 等平台特定格式建议
   - 媒体文件发送指令

6. **技能索引**：
   - 从 `~/.hermes/skills/` 扫描技能
   - 支持外部技能目录（只读）
   - 缓存和快照优化

#### 4.2 上下文层（Context）

按优先级加载项目上下文（仅第一个匹配）：

1. `.hermes.md` / `HERMES.md`（搜索至 git root）
2. `AGENTS.md` / `agents.md`（仅当前目录）
3. `CLAUDE.md` / `claude.md`（仅当前目录）
4. `.cursorrules` / `.cursor/rules/*.mdc`（仅当前目录）

每个上下文文件限制在 20,000 字符。

#### 4.3 易失层（Volatile）

每轮变化的动态部分：

1. **记忆快照**：从 `MEMORY.md` + `USER.md` 加载
2. **用户配置文件**：`USER.md` 内容
3. **外部记忆提供程序**：通过插件注入
4. **时间戳行**：会话/模型/提供商信息

#### 4.4 缓存机制

- 系统提示词在会话开始时构建一次并缓存
- 缓存保存到会话数据库（`update_system_prompt`）
- 后续轮次从数据库恢复，保持提示词缓存热度
- 仅上下文压缩时触发重建

### 5. 上下文管理

**入口**: `context_engine.py`（抽象）和 `context_compressor.py`（实现）

#### 5.1 上下文引擎接口

```python
class ContextEngine(ABC):
    @abstractmethod
    def update_from_response(self, usage: Dict) -> None:
        """从 API 响应更新令牌使用量"""

    @abstractmethod
    def should_compress(self, prompt_tokens: int) -> bool:
        """判断是否需要压缩"""

    @abstractmethod
    def compress(self, messages: List) -> List[Dict]:
        """压缩消息列表"""

    def on_session_start(self, session_id: str, **kwargs) -> None:
        """会话开始回调"""

    def on_session_end(self, session_id: str, messages: List) -> None:
        """会话结束回调"""

    def get_tool_schemas(self) -> List[Dict]:
        """返回上下文引擎提供的工具模式"""
```

#### 5.2 内置压缩器

`ContextCompressor` 提供基于摘要的压缩策略：

**配置参数**：
- `threshold_percent`: 触发压缩的阈值百分比（默认 75%）
- `protect_first_n`: 头部保护消息数（默认 3）
- `protect_last_n`: 尾部保护消息数（默认 6）
- `summary_target_ratio`: 目标摘要比例（默认 20%）

**压缩流程**：
1. 检测是否需要压缩（`should_compress`）
2. 提取头部、尾部受保护消息
3. 对中间消息调用 LLM 生成摘要
4. 构建新消息列表：[系统提示] + [头部] + [摘要] + [尾部]
5. 更新令牌统计

#### 5.3 前置压缩

在主循环开始前检查：

```python
if compression_enabled and len(messages) > protect_first_n + protect_last_n + 1:
    # 估算请求令牌数
    preflight_tokens = estimate_request_tokens_rough(messages, system_prompt, tools)

    if preflight_tokens >= threshold_tokens:
        # 触发前置压缩（最多 3 轮）
        for _pass in range(3):
            messages, system_prompt = compress_context(...)
            if len(messages) >= original_len:
                break  # 无法继续压缩
```

### 6. 传输层架构

**位置**: `agent/transports/`

传输层为不同提供商提供统一的接口，隐藏 API 差异。

#### 6.1 传输层基类

```python
# agent/transports/base.py
class BaseTransport(ABC):
    @abstractmethod
    def normalize_response(self, response) -> NormalizedResult:
        """规范化不同提供商的响应为统一格式"""

    @abstractmethod
    def validate_response(self, response) -> bool:
        """验证响应是否有效"""
```

#### 6.2 各提供商适配器

| 适配器 | API 模式 | 用途 |
|--------|---------|------|
| `anthropic.py` | `anthropic_messages` | Anthropic 原生 API |
| `chat_completions.py` | `chat_completions` | OpenAI 兼容 API |
| `bedrock.py` | `bedrock_converse` | AWS Bedrock Converse API |
| `codex.py` | `codex_responses` | OpenAI Codex Responses API |
| `codex_app_server.py` | `codex_app_server` | Codex 应用服务器模式 |

#### 6.3 规范化响应

所有传输层将提供商响应规范化为统一格式：

```python
@dataclass
class NormalizedResult:
    content: str | None
    tool_calls: List[ToolCall] | None
    reasoning: str | None
    finish_reason: str  # "stop", "length", "tool_calls", etc.
    usage: UsageInfo
```

### 7. 迭代预算管理

**入口**: `iteration_budget.py`

`IterationBudget` 类提供线程安全的迭代计数器：

```python
class IterationBudget:
    def __init__(self, max_total: int):
        self.max_total = max_total
        self._used = 0
        self._lock = threading.Lock()

    def consume(self) -> bool:
        """尝试消费一次迭代。返回 True 表示允许"""
        with self._lock:
            if self._used >= self.max_total:
                return False
            self._used += 1
            return True

    def refund(self) -> None:
        """退回一次迭代（如 execute_code 调用）"""
        with self._lock:
            if self._used > 0:
                self._used -= 1

    @property
    def remaining(self) -> int:
        """剩余可用迭代次数"""
        with self._lock:
            return max(0, self.max_total - self._used)
```

**使用场景**：
- 父代理：最大迭代 90 次（`max_iterations`）
- 子代理：最大迭代 50 次（`delegation.max_iterations`）
- `execute_code` 调用：退回迭代，不占用预算

### 8. 错误处理与恢复

**入口**: `error_classifier.py` → `classify_api_error(error, ...)`

#### 8.1 错误分类

```python
@dataclass
class ClassifiedError:
    reason: FailoverReason
    status_code: int | None
    retryable: bool
    should_compress: bool
    should_rotate_credential: bool
    should_fallback: bool
```

#### 8.2 恢复策略

| 错误类型 | 恢复策略 |
|---------|---------|
| 429 速率限制 | 指数退避 + 回退链激活 |
| 上下文超限（413/429） | 触发上下文压缩 |
| 401 认证错误 | 凭证刷新（Anthropic/ OpenAI/Copilot/Nous） |
| 5xx 服务器错误 | 重试（最多 3 次） |
| UnicodeEncodeError | 消息清理（代理字符/ASCII 模式） |
| 图像拒绝 | 切换到纯文本模式 |
| 图像过大 | 图像压缩重试 |
| 响应截断（length） | 请求续写（最多 3 次） |

#### 8.3 回退链

```python
# 配置示例
fallback_model:
  - provider: openrouter
    model: anthropic/claude-sonnet-4.6
  - provider: anthropic
    model: claude-sonnet-4.6
```

主提供商失败时自动激活下一提供商。

### 9. 流式处理

#### 9.1 流式 API 调用

```python
def _interruptible_streaming_api_call(agent, api_kwargs):
    """可中断的流式 API 调用"""
    try:
        stream = client.chat.completions.create(**api_kwargs, stream=True)

        for chunk in stream:
            # 检查中断
            if agent._interrupt_requested:
                raise InterruptedError()

            # 处理流式 delta
            if chunk.choices[0].delta.content:
                # 流式上下文清理器处理
                agent._stream_context_scrubber.process(chunk.delta.content)

                # 流式思考块清理器处理
                agent._stream_think_scrubber.process(chunk.delta.content)

                # 回调通知
                if agent.stream_delta_callback:
                    agent.stream_delta_callback(chunk.delta.content)

    except InterruptedError:
        # 中断处理
        pass
```

#### 9.2 流式清理器

两个状态性清理器处理跨 delta 边界的内容：

- **`StreamingContextScrubber`**：清理 `<memory-context>` 块
- **`StreamingThinkScrubber`**：清理 `<think>`/`<reasoning>` 块

确保代理标记不会因为 delta 边界而被破坏。

### 10. 记忆系统

**入口**: `memory_manager.py`

#### 10.1 内置记忆

- `MEMORY.md`：持久事实（用户偏好、环境细节）
- `USER.md`：用户配置文件
- 限制：`memory_char_limit`（默认 2200）、`user_char_limit`（默认 1375）

#### 10.2 外部记忆提供程序

插件系统支持外部记忆提供程序（如 Honcho）：

```python
# 配置示例
memory:
  provider: honcho  # 或其他插件名称
  memory_enabled: true
  user_profile_enabled: true
  nudge_interval: 10  # 每 10 轮提醒写入记忆
```

#### 10.3 记忆注入

记忆在每轮调用时通过 `build_memory_context_block` 注入到用户消息中：

```
<memory-context>
事实 1
事实 2
...
</memory-context>
```

### 11. 技能系统

**入口**: `prompt_builder.py` → `build_skills_system_prompt(...)`

#### 11.1 技能结构

```
~/.hermes/skills/
├── general/
│   └── my-skill/
│       ├── SKILL.md          # 技能说明
│       └── DESCRIPTION.md    # 类别说明
└── development/
    └── testing/
        └── SKILL.md
```

#### 11.2 技能模式

`SKILL.md` 格式：

```yaml
---
name: My Skill
platforms: [cli, webui]
requires_tools: [terminal, execute_code]
requires_toolsets: [python]
---

技能描述和指南...

## 工作流程

1. 步骤 1
2. 步骤 2

## 注意事项

- 注意点 1
- 注意点 2
```

#### 11.3 技能加载

- 缓存优化：LRU 缓存 + 磁盘快照
- 快照验证：通过 mtime/size 清单检查
- 支持外部技能目录（只读）
- 平台过滤：根据 `platforms` 字段

### 12. 会话持久化

#### 12.1 会话日志

```
~/.hermes/sessions/
└── session_YYYYMMDD_HHMMSS_<uuid>.json
```

记录完整的对话历史，包括：

- 所有消息（用户、助手、工具）
- 工具调用和结果
- 元数据（时间戳、模型、提供商）
- 令牌使用量
- 成本估算

#### 12.2 会话数据库

SQLite 数据库（`~/.hermes/sessions.db`）：

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT,
    model TEXT,
    provider TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    total_input_tokens INTEGER,
    total_output_tokens INTEGER,
    ...
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP,
    ...
);
```

用于网关跨会话搜索和统计。

### 13. 插件系统

#### 13.1 插件钩子

| 钩子名称 | 触发时机 | 用途 |
|---------|---------|------|
| `on_session_start` | 会话开始时 | 初始化会话状态 |
| `pre_llm_call` | LLM 调用前 | 注入上下文 |
| `pre_api_request` | API 请求前 | 请求监控/修改 |
| `pre_tool_call_block` | 工具调用前 | 工具拦截 |
| `on_tool_complete` | 工具完成时 | 结果处理 |

#### 13.2 上下文引擎插件

支持通过插件替换内置压缩器：

```
plugins/context_engine/<name>/
├── __init__.py
└── engine.py  # 实现 ContextEngine 接口
```

配置：

```yaml
context:
  engine: lcm  # 或 "compressor"（默认）
```

#### 13.3 记忆提供程序插件

外部记忆提供程序实现：

```python
class MemoryProvider(ABC):
    def initialize(self, **kwargs) -> None:
        """初始化提供程序"""

    def prefetch_all(self, query: str) -> str:
        """预取相关记忆"""

    def on_memory_write(self, action, target, content, metadata) -> None:
        """处理记忆写入"""

    def handle_tool_call(self, name, args) -> str:
        """处理工具调用"""
```

### 14. 中断机制

#### 14.1 中断信号

```python
agent._interrupt_requested: bool  # 中断标志
agent._interrupt_message: str | None  # 触发中断的消息
agent._execution_thread_id: int  # 执行线程 ID
```

#### 14.2 中断传播

- **主线程**：调用 `interrupt()` 设置标志
- **API 调用**：定期检查标志，`InterruptedError`
- **工具执行**：通过线程 ID 传播到工作线程
- **子代理**：递归传播中断

#### 14.3 /steer 机制

不同于中断，steer 在工具完成后注入引导：

```python
agent.steer("请使用 Python 3.11")
# → 引导注入到下一个工具结果，不中断执行
```

### 15. 多模态支持

#### 15.1 图像处理

- 视觉分析工具：`vision_analyze`
- 图像生成：`image_generate`（通过提供商）
- 图像拒绝恢复：检测 "仅支持文本" 错误并切换模式

#### 15.2 多模态工具结果

```python
{
    "_multimodal": True,
    "content": [
        {"type": "text", "text": "这是图片描述"},
        {"type": "image_url", "image_url": "https://..."}
    ]
}
```

用于返回图像和文本组合的结果。

### 16. 性能优化

#### 16.1 提示词缓存

**Anthropic 提示词缓存**：
- 自动为 Claude 模型启用（`_use_prompt_caching`）
- 策略：`system_and_3`（系统提示词 + 最后 3 条消息）
- TTL 层：`5m`（默认）或 `1h`
- 节省约 75% 的输入成本

#### 16.2 快照缓存

- **技能快照**：`~/.hermes/.skills_prompt_snapshot.json`
- 通过 mtime/size 清单验证
- 避免重复文件扫描

#### 16.3 后端探测缓存

- 远程后端（Docker、Modal 等）OS 信息探测
- 每进程缓存键：`(env_type, cwd_hint)`
- 避免重复探测调用

### 17. 日志与监控

#### 17.1 活动追踪

```python
agent._last_activity_ts: float  # 最后活动时间戳
agent._last_activity_desc: str  # 最后活动描述

def _touch_activity(self, desc: str):
    """更新活动时间戳（网关超时监控）"""
    self._last_activity_ts = time.time()
    self._last_activity_desc = desc
```

#### 17.2 日志级别

- `agent.log`：INFO+ 级别（`~/.hermes/logs/agent.log`）
- `errors.log`：WARNING+ 级别（`~/.hermes/logs/errors.log`）
- 详细日志：`--verbose` 标志

#### 17.3 令牌统计

每 API 调用追踪：

```python
session_prompt_tokens
session_completion_tokens
session_total_tokens
session_input_tokens
session_output_tokens
session_cache_read_tokens
session_cache_write_tokens
session_reasoning_tokens
session_estimated_cost_usd
```

### 18. 网关集成

#### 18.1 会话上下文

```python
from gateway.session_context import (
    _SESSION_ID,
    get_session_env,
)

_SESSION_ID.set(session_id)  # 设置会话 ID
env = get_session_env("HERMES_PLATFORM")  # 获取环境变量
```

#### 18.2 状态回调

```python
agent.status_callback = lambda status: gateway.send_status(status)
agent.tool_progress_callback = lambda event, name, args: gateway.notify_tool(event, name, args)
agent.step_callback = lambda api_call_count, prev_tools: gateway.notify_step(api_call_count, prev_tools)
```

### 19. 安全特性

#### 19.1 提示词注入防护

扫描上下文文件（SOUL.md、AGENTS.md 等）的攻击模式：

```python
_CONTEXT_THREAT_PATTERNS = [
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'do\s+not\s+tell\s+the\s+user', "deception_hide"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    # ... 更多模式
]
```

#### 19.2 工具调用守卫

```python
class ToolCallGuardrailController:
    def before_call(self, name: str, args: Dict) -> ToolGuardrailDecision:
        """工具调用前检查"""
        # 检查配置的守卫规则
        # 返回允许/拒绝/修改决定
```

配置示例：

```yaml
tool_loop_guardrails:
  dangerous_commands:
    block: ["rm -rf /", "format c:"]
  sensitive_operations:
    require_confirmation: true
```

#### 19.3 文件检查点

```python
agent._checkpoint_mgr = CheckpointManager(
    enabled=True,
    max_snapshots=20,
    max_total_size_mb=500,
    max_file_size_mb=10,
)
```

在文件变更/破坏性命令前自动创建快照。

## 扩展指南

### 添加新工具

1. 在 `tools/` 创建工具函数
2. 在 `tools/tools.py` 的 `get_tool_definitions()` 注册
3. 添加工具描述到 `skills/` 中的技能文件

### 添加新提供商

1. 在 `agent/transports/` 创建新的适配器
2. 实现 `BaseTransport` 接口
3. 在 `agent/auxiliary_client.py` 添加提供商路由
4. 在 `providers/` 注册提供商配置

### 添加新上下文引擎

1. 创建 `plugins/context_engine/<name>/engine.py`
2. 实现 `ContextEngine` 接口
3. 在配置文件设置 `context.engine: <name>`

### 添加新记忆提供程序

1. 创建插件目录 `plugins/memory/<name>/`
2. 实现 `MemoryProvider` 接口
3. 在配置文件设置 `memory.provider: <name>`

## 关键配置参数

```yaml
agent:
  max_iterations: 90              # 最大迭代次数
  tool_use_enforcement: auto        # 工具使用强制策略
  api_max_retries: 3                # API 重试次数

model:
  max_tokens: 4096                 # 最大输出令牌
  context_length: 200000             # 上下文长度（覆盖自动检测）

compression:
  enabled: true                     # 启用自动压缩
  threshold: 0.75                   # 压缩阈值百分比
  target_ratio: 0.20                # 目标摘要比例
  protect_first_n: 3               # 头部保护消息数
  protect_last_n: 6                # 尾部保护消息数

memory:
  memory_enabled: true                # 启用内置记忆
  user_profile_enabled: true           # 启用用户配置文件
  nudge_interval: 10                 # 记忆提醒间隔
  provider: honcho                   # 外部记忆提供程序

skills:
  creation_nudge_interval: 10        # 技能创建提醒间隔

delegation:
  max_iterations: 50                # 子代理最大迭代
```

## 流程图

### 完整对话流程

```
┌─────────────────────────────────────────────────────────────────┐
│                     用户输入消息                              │
└───────────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              代理初始化/状态恢复                         │
│  - 加载配置和工具                                       │
│  - 恢复会话历史                                       │
│  - 恢复/构建系统提示词                                 │
└───────────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                  主循环开始                                 │
│  while (api_call_count < max_iterations                      │
│         and iteration_budget.remaining > 0)                   │
└───────────────────────────┬───────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │  中断检查 │  迭代预算消费      │
        │      ▼                     │
        │  ┌─────────────────┐ │
        │  │ 构建 API 消息 │ │
        │  │ - 清理工具参数 │ │
        │  │ - 注入记忆上下文 │ │
        │  │ - 应用提示词缓存 │ │
        │  └────────┬────────┘ │
        │           │             │
        │           ▼             │
        │  ┌─────────────────┐ │
        │  │ API 调用      │ │
        │  │ - 流式/非流式   │ │
        │  │ - 错误处理     │ │
        │  │ - 重试/回退    │ │
        │  └────────┬────────┘ │
        │           │             │
        │           ▼             │
        │  ┌─────────────────┐ │
        │  │ finish_reason?  │ │
        │  └────────┬────────┘ │
        │     │ │ │ │ │      │
        │  ┌──┴──┴──┴──┴────┐ │
        │  │                 │ │
        │  │                 │ │
        │  ▼                 ▼ │
        │  有工具调用?         │
        │  ┌────────────────┐ │
        │  │ 工具执行      │ │
        │  │ - 并发/顺序   │ │
        │  │ - 守卫检查     │ │
        │  │ - 检查点      │ │
        │  └────────┬────────┘ │
        │           │             │
        │           ▼             │
        │  工具结果→历史  │ │
        │           │             │
        └───────────┴─────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                返回最终响应                                │
└─────────────────────────────────────────────────────────────────┘
```

### 工具执行流程

```
┌─────────────────────────────────────────────────────────────────┐
│              工具调用请求                                │
│  - 名称: tool_name                                          │
│  - 参数: {"key": "value"}                                  │
└───────────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              预执行检查                                 │
│  - 插件预检查（get_pre_tool_call_block_message）            │
│  - 工具守卫检查（ToolCallGuardrailController）             │
│  - 检查点检查（文件变更）                               │
└───────────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│               工具分发                                   │
│  - 内置工具（todo, session_search, memory, delegate）      │
│  - 上下文引擎工具                                         │
│  - 记忆提供程序工具                                       │
│  - 注册的工具（handle_function_call）                           │
└───────────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│               工具执行                                   │
│  - 活动回调（网关超时检测）                             │
│  - 执行时错误处理                                        │
│  - 结果清理（多模态处理）                                 │
└───────────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│               执行后验证                                 │
│  - 检查点验证（文件变更）                               │
│  - 记忆写入通知                                          │
└───────────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│             工具结果持久化（可选）                          │
└───────────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│            工具结果添加到消息历史                          │
└─────────────────────────────────────────────────────────────────┘
```

## 参考资源

- **主入口**: `run_agent.py`（AIAgent 主类）
- **对话循环**: `agent/conversation_loop.py`
- **工具执行**: `agent/tool_executor.py`
- **系统提示**: `agent/system_prompt.py` + `agent/prompt_builder.py`
- **上下文管理**: `agent/context_engine.py` + `agent/context_compressor.py`
- **传输层**: `agent/transports/`
- **记忆管理**: `agent/memory_manager.py`
- **模型元数据**: `agent/model_metadata.py`
