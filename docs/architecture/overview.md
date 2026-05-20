# Hermes Agent 整体架构

## 系统概览

Hermes Agent 是一个自进化 AI 代理系统，采用模块化设计，支持多平台交互、闭环学习、定时自动化等核心功能。

```mermaid
graph TB
    User[用户] --> CLI[CLI 终端界面]
    User --> Platforms[消息平台<br/>Telegram/Discord/Slack/等]
    
    CLI --> Gateway[消息网关<br/>Gateway]
    Platforms --> Gateway
    
    Gateway --> AgentLoop[Agent 对话循环<br/>Conversation Loop]
    
    subgraph Core[核心系统]
        AgentLoop
        Memory[记忆系统<br/>Memory System]
        Skills[技能系统<br/>Skill System]
        Tools[工具系统<br/>Tool System]
        Models[模型适配层<br/>Model Adapter]
        Context[上下文引擎<br/>Context Engine]
    end
    
    AgentLoop <--> Memory
    AgentLoop <--> Skills
    AgentLoop <--> Tools
    AgentLoop <--> Context
    AgentLoop --> Models
    
    subgraph External[外部系统]
        Models --> LLM[LLM 提供商<br/>Anthropic/OpenAI/等]
        Tools --> Env[执行环境<br/>Docker/SSH/Modal/等]
        Cron[定时调度器<br/>Cron Scheduler] --> Gateway
    end
    
    Memory --> Storage[(持久化存储<br/>SQLite/JSON)]
```

## 核心模块说明

### 1. 消息网关 (Gateway)
- 负责与各种消息平台的连接和通信
- 支持多平台适配器模式
- 管理会话生命周期和消息路由
- 流式传输支持

### 2. Agent 对话循环
- 核心消息处理逻辑
- 协调工具调用和技能执行
- 上下文管理和对话压缩
- 工具调用决策和执行

### 3. 记忆系统
- 跨会话记忆存储和检索
- 用户建模和个性化
- 对话历史摘要
- FTS5 全文搜索支持

### 4. 技能系统
- 技能创建和管理
- 技能改进和优化
- 技能发现和加载
- 过程记忆管理

### 5. 工具系统
- 40+ 内置工具
- 工具执行环境隔离
- 终端后端支持 (Docker/SSH/Modal 等)
- MCP 服务器集成

### 6. 模型适配层
- 支持 200+ 模型
- 多提供商统一接口
- 提示词缓存
- 流式输出支持

## 架构特点

```mermaid
graph LR
    A[模块化设计] --> B[可扩展性]
    C[平台无关] --> D[多端接入]
    E[闭环学习] --> F[自我进化]
    G[隔离执行] --> H[安全性]
    I[持久化存储] --> J[数据可靠性]
```

### 关键设计原则

1. **模块化**：各系统独立开发和测试
2. **可扩展**：支持新平台、新模型、新工具的轻松集成
3. **安全隔离**：工具执行在隔离环境中
4. **状态持久化**：会话、记忆、技能均持久化存储
5. **流式优先**：支持实时流式响应
6. **并发安全**：使用 ContextVar 实现任务级状态隔离

## 数据流

```mermaid
sequenceDiagram
    participant User as 用户
    participant Gateway as 消息网关
    participant Agent as Agent循环
    participant Memory as 记忆系统
    participant Tools as 工具系统
    participant LLM as LLM
    
    User->>Gateway: 发送消息
    Gateway->>Gateway: 会话识别/创建
    Gateway->>Memory: 获取历史上下文
    Memory-->>Gateway: 返回历史
    Gateway->>Agent: 开始处理
    Agent->>Agent: 构建提示词
    Agent->>LLM: 发送请求
    LLM-->>Agent: 返回响应
    alt 需要工具调用
        Agent->>Tools: 执行工具
        Tools-->>Agent: 返回结果
        Agent->>LLM: 发送工具结果
        LLM-->>Agent: 返回最终响应
    end
    Agent->>Memory: 保存新交互
    Agent->>Gateway: 返回响应
    Gateway->>User: 发送消息
```

## 部署架构

```mermaid
graph TB
    subgraph Client[客户端层]
        T[Telegram]
        D[Discord]
        S[Slack]
        C[CLI]
        W[Web]
    end
    
    subgraph Server[服务层]
        GW[Gateway 进程]
        Cron[Cron Scheduler]
    end
    
    subgraph Storage[存储层]
        DB[(SQLite DB)]
        FS[(文件系统)]
        Cache[(缓存)]
    end
    
    subgraph External[外部服务]
        LLM[LLM API]
        Tools[外部工具 API]
        Env[执行环境]
    end
    
    Client --> Server
    Server --> Storage
    Server --> External
```

## 相关文档

- [网关架构](./gateway-architecture.md)
- [对话流程](./conversation-flow.md)
- [技能系统](./skill-system.md)
- [记忆系统](./memory-system.md)
- [技术栈](../tech-stack.md)
