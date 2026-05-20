# 对话流程

本文档详细描述 Hermes Agent 从接收用户消息到发送响应的完整对话处理流程。

## 完整对话流程图

```mermaid
sequenceDiagram
    autonumber
    participant User as 用户
    participant Platform as 平台适配器
    participant Gateway as 网关核心
    participant Session as 会话管理
    participant Context as 上下文引擎
    participant Agent as Agent 循环
    participant LLM as LLM 模型
    participant Tools as 工具系统
    participant Memory as 记忆系统

    Note over User,Memory: 消息接收阶段
    User->>Platform: 发送消息
    Platform->>Platform: 解析消息事件
    Platform->>Gateway: 传递 MessageEvent
    
    Note over Gateway,Session: 会话识别阶段
    Gateway->>Session: 构建会话键
    Session->>Session: 查找/创建会话
    alt 新会话
        Session->>Memory: 初始化会话记忆
    end
    Session-->>Gateway: 返回会话上下文
    
    Note over Gateway,Context: 上下文构建阶段
    Gateway->>Context: 加载对话历史
    Gateway->>Context: 添加上下文文件
    Gateway->>Context: 应用提示词模板
    Context->>Context: 上下文压缩（如需要）
    Context-->>Gateway: 返回完整提示词
    
    Note over Gateway,LLM: Agent 处理阶段
    Gateway->>Agent: 开始对话循环
    Agent->>LLM: 发送初始请求
    LLM-->>Agent: 返回响应（可能含工具调用）
    
    alt 工具调用
        loop 工具调用循环
            Agent->>Tools: 执行工具
            Tools->>Tools: 环境准备
            Tools->>Tools: 执行命令/操作
            Tools-->>Agent: 返回工具结果
            Agent->>LLM: 发送工具结果
            LLM-->>Agent: 返回下一响应
        end
    end
    
    Note over Agent,Memory: 响应处理阶段
    Agent->>Agent: 生成最终响应
    Agent->>Memory: 保存交互记录
    Agent->>Memory: 更新用户画像
    Agent-->>Gateway: 返回响应
    
    Note over Gateway,User: 响应发送阶段
    alt 流式传输
        Gateway->>Platform: 开始流式发送
        loop 增量发送
            Gateway->>Platform: 发送文本增量
            Platform->>User: 更新消息
        end
        Gateway->>Platform: 完成流式发送
    else 非流式
        Gateway->>Platform: 发送完整响应
        Platform->>User: 显示消息
    end
    
    Note over Gateway,Session: 会话收尾阶段
    Gateway->>Session: 检查重置策略
    alt 需要重置
        Session->>Session: 重置会话
        Session->>Memory: 归档旧会话
    end
    Session->>Session: 更新会话元数据
```

## 详细流程说明

### 1. 消息接收阶段

```mermaid
graph TD
    A[平台接收消息] --> B{消息类型判断}
    B -->|文本| C[解析文本内容]
    B -->|媒体| D[下载媒体文件]
    B -->|命令| E[解析斜杠命令]
    B -->|贴纸| F[查询贴纸缓存]
    C --> G[创建 MessageEvent]
    D --> G
    E --> G
    F --> G
    G --> H[添加元数据]
    H --> I[传递给网关]
```

**关键点：**
- 支持多种消息类型：文本、图片、语音、文档、贴纸等
- 自动转写语音消息（如启用）
- 解析平台特定事件（按钮交互、话题等）

### 2. 会话识别阶段

会话键构建规则：

```mermaid
graph LR
    A[会话源] --> B{会话类型}
    B -->|DM| C[agent:main:{platform}:dm:{chat_id}]
    B -->|群聊隔离| D[agent:main:{platform}:group:{chat_id}:{user_id}]
    B -->|群聊共享| E[agent:main:{platform}:group:{chat_id}]
    B -->|线程| F[agent:main:{platform}:thread:{thread_id}]
    C --> G{会话存在?}
    D --> G
    E --> G
    F --> G
    G -->|是| H[加载现有会话]
    G -->|否| I[创建新会话]
    H --> J[检查会话状态]
    I --> J
    J --> K{是否挂起?}
    K -->|是| L[拒绝处理]
    K -->|否| M[继续处理]
```

### 3. 上下文构建阶段

```mermaid
graph TB
    A[开始构建上下文] --> B[加载系统提示词]
    B --> C[添加人格设定]
    C --> D[加载对话历史]
    D --> E{历史过长?}
    E -->|是| F[上下文压缩]
    E -->|否| G[添加上下文文件]
    F --> G
    G --> H[添加平台特定信息]
    H --> I[添加频道上下文]
    I --> J[添加技能提示]
    J --> K[构建完成]
```

**上下文组成部分：**
- 系统提示词（核心指令）
- 人格设定（SOUL.md）
- 对话历史（最近 N 轮）
- 上下文文件（项目相关文件）
- 平台特定提示
- 频道上下文
- 技能相关提示

### 4. Agent 处理阶段

```mermaid
stateDiagram-v2
    [*] --> INIT: 初始化
    INIT --> THINKING: 发送提示到 LLM
    THINKING --> TOOL_CALL: 收到工具调用
    THINKING --> FINAL: 收到最终响应
    TOOL_CALL --> EXECUTING: 执行工具
    EXECUTING --> THINKING: 返回工具结果
    FINAL --> [*]: 完成
    
    state EXECUTING {
        [*] --> PREPARE: 准备环境
        PREPARE --> RUN: 执行操作
        RUN --> CAPTURE: 捕获输出
        CAPTURE --> SANITIZE: 清理结果
        SANITIZE --> [*]
    }
```

**迭代预算：**
- 默认最大迭代次数：通常为 20-30 步
- 可配置的迭代限制
- 自动检测循环和停滞

### 5. 响应发送阶段

```mermaid
graph TB
    A[准备响应] --> B{流式传输启用?}
    B -->|是| C{平台支持流式?}
    B -->|否| D[发送完整消息]
    C -->|是| E[原生草稿模式]
    C -->|否| F[编辑模式]
    E --> G[开始流式发送]
    F --> G
    G --> H[缓冲文本增量]
    H --> I{达到阈值?}
    I -->|是| J[发送更新]
    I -->|否| H
    J --> K{还有更多?}
    K -->|是| H
    K -->|否| L[完成发送]
    D --> M[保存消息 ID]
    L --> M
```

**流式传输模式：**
- `auto`：自动选择最佳模式
- `draft`：原生草稿流式（Telegram Bot API 9.5+）
- `edit`：渐进式编辑消息
- `off`：禁用流式

### 6. 会话收尾阶段

```mermaid
graph TD
    A[处理完成] --> B{检查重置策略}
    B -->|daily| C{到达重置时间?}
    B -->|idle| D{超时?}
    B -->|both| E{任一条件满足?}
    B -->|none| F[保持会话]
    C -->|是| G[重置会话]
    D -->|是| G
    E -->|是| G
    C -->|否| F
    D -->|否| F
    E -->|否| F
    G --> H[保存会话摘要]
    H --> I[归档旧消息]
    F --> J[更新最后活动时间]
    I --> J
    J --> K[保存会话元数据]
```

## 会话重置策略

| 策略 | 说明 | 配置 |
|------|------|------|
| `daily` | 每日定时重置 | `at_hour`（默认 4 点） |
| `idle` | 空闲超时重置 | `idle_minutes`（默认 1440） |
| `both` | 任一条件满足即重置 | 两者都配置 |
| `none` | 永不自动重置 | 手动 `/reset` |

## 上下文压缩

当对话历史过长时，系统会自动压缩上下文：

```mermaid
graph LR
    A[检测上下文长度] --> B{超过阈值?}
    B -->|否| C[使用完整历史]
    B -->|是| D[开始压缩]
    D --> E[保留最近 N 轮]
    D --> F[摘要早期消息]
    D --> G[保留系统消息]
    D --> H[保留关键工具调用]
    E --> I[合并压缩结果]
    F --> I
    G --> I
    H --> I
    I --> J[验证长度]
    J --> K{仍过长?}
    K -->|是| L[进一步压缩]
    K -->|否| M[完成]
    L --> M
```

## 错误处理流程

```mermaid
graph TD
    A[发生错误] --> B{错误类型}
    B -->|网络错误| C[重试请求]
    B -->|工具错误| D[向 LLM 报告错误]
    B -->|安全错误| E[拒绝执行]
    B -->|会话错误| F[重置会话]
    C --> G{重试成功?}
    G -->|是| H[继续处理]
    G -->|否| I[降级处理]
    D --> H
    E --> J[通知用户]
    F --> H
    I --> J
```

## 相关文档

- [整体架构](./overview.md)
- [工具调用流程](./tool-call-flow.md)
- [网关架构](./gateway-architecture.md)
- [记忆系统](./memory-system.md)
