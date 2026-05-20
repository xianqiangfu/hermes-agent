# 工具调用流程

本文档详细描述 Hermes Agent 的工具调用系统，包括工具注册、执行、错误处理等完整流程。

## 工具调用总览图

```mermaid
sequenceDiagram
    autonumber
    participant LLM as LLM 模型
    participant Agent as Agent 循环
    participant ToolReg as 工具注册表
    participant Guard as 工具防护
    participant Exec as 工具执行器
    participant Env as 执行环境
    participant Storage as 结果存储

    LLM->>Agent: 返回工具调用请求
    Agent->>ToolReg: 查找工具定义
    ToolReg-->>Agent: 返回工具信息
    
    Agent->>Guard: 验证工具调用
    Guard->>Guard: 检查权限
    Guard->>Guard: 检查参数
    Guard->>Guard: 检查安全策略
    
    alt 验证通过
        Guard-->>Agent: 允许执行
        Agent->>Exec: 提交执行请求
        Exec->>Env: 准备执行环境
        Env->>Env: 隔离配置
        Env-->>Exec: 环境就绪
        Exec->>Exec: 参数验证
        Exec->>Env: 执行工具逻辑
        Env->>Env: 捕获输出/错误
        Env-->>Exec: 返回执行结果
        Exec->>Storage: 存储工具结果
        Storage-->>Exec: 确认存储
        Exec-->>Agent: 返回工具结果
    else 验证失败
        Guard-->>Agent: 返回拒绝原因
    end
    
    Agent->>LLM: 发送工具结果/拒绝信息
```

## 工具系统架构

```mermaid
graph TB
    subgraph Interface[接口层]
        ToolDef[工具定义]
        ToolSchema[参数 Schema]
        ToolExamples[使用示例]
    end
    
    subgraph Registry[注册层]
        ToolRegistry[工具注册表]
        ToolDiscovery[工具发现]
        ToolLoader[工具加载器]
    end
    
    subgraph GuardRail[防护层]
        Permission[权限检查]
        Safety[安全检查]
        Approval[审批流程]
        Budget[预算控制]
    end
    
    subgraph Execution[执行层]
        Executor[执行器]
        EnvManager[环境管理]
        Isolation[隔离机制]
        Timeout[超时控制]
    end
    
    subgraph Storage[存储层]
        ResultCache[结果缓存]
        History[执行历史]
        Provenance[来源追踪]
    end
    
    Interface --> Registry
    Registry --> GuardRail
    GuardRail --> Execution
    Execution --> Storage
```

## 工具执行详细流程

### 1. 工具调用请求解析

```mermaid
graph TD
    A[接收工具调用] --> B[解析工具名称]
    B --> C{工具存在?}
    C -->|否| D[返回错误]
    C -->|是| E[获取工具定义]
    E --> F[解析参数 JSON]
    F --> G{参数有效?}
    G -->|否| H[返回参数错误]
    G -->|是| I[准备验证]
```

### 2. 安全检查与权限验证

```mermaid
graph LR
    A[开始验证] --> B{需要审批?}
    B -->|是| C[检查审批白名单]
    B -->|否| D[权限检查]
    C --> E{已批准?}
    E -->|否| F[请求用户审批]
    E -->|是| D
    F --> G{用户批准?}
    G -->|否| H[拒绝执行]
    G -->|是| D
    D --> I[参数安全检查]
    I --> J{参数安全?}
    J -->|否| H
    J -->|是| K[检查预算]
    K --> L{预算充足?}
    L -->|否| H
    L -->|是| M[验证通过]
```

### 3. 执行环境准备

```mermaid
graph TB
    A[选择执行后端] --> B{后端类型}
    B -->|local| C[本地环境]
    B -->|docker| D[Docker 容器]
    B -->|ssh| E[SSH 远程]
    B -->|modal| F[Modal Serverless]
    B -->|daytona| G[Daytona]
    C --> H[准备工作目录]
    D --> H
    E --> H
    F --> H
    G --> H
    H --> I[设置环境变量]
    I --> J[文件同步]
    J --> K[环境就绪]
```

**支持的执行后端：**

| 后端 | 说明 | 隔离级别 |
|------|------|----------|
| `local` | 本地直接执行 | 低 |
| `docker` | Docker 容器 | 高 |
| `ssh` | 远程 SSH 服务器 | 中 |
| `modal` | Modal Serverless | 高 |
| `daytona` | Daytona 开发环境 | 中 |
| `singularity` | Singularity 容器 | 高 |

### 4. 工具执行

```mermaid
stateDiagram-v2
    [*] --> PENDING: 等待执行
    PENDING --> RUNNING: 开始执行
    RUNNING --> RUNNING: 执行中
    RUNNING --> SUCCESS: 执行成功
    RUNNING --> FAILED: 执行失败
    RUNNING --> TIMEOUT: 超时
    RUNNING --> CANCELLED: 被取消
    
    SUCCESS --> [*]
    FAILED --> [*]
    TIMEOUT --> [*]
    CANCELLED --> [*]
```

### 5. 结果处理与存储

```mermaid
graph TD
    A[接收执行结果] --> B{执行状态}
    B -->|成功| C[处理成功结果]
    B -->|失败| D[处理错误结果]
    B -->|超时| E[处理超时]
    C --> F{结果过大?}
    F -->|是| G[截断/存储到文件]
    F -->|否| H[保留完整结果]
    D --> I[分类错误类型]
    E --> J[清理超时进程]
    G --> K[存储结果]
    H --> K
    I --> K
    J --> K
    K --> L[更新执行历史]
    L --> M[返回给 Agent]
```

## 内置工具分类

```mermaid
mindmap
  root((Hermes Tools))
    文件操作
      读文件
      写文件
      编辑文件
      文件搜索
      目录浏览
    终端执行
      Shell 命令
      代码执行
      环境管理
    浏览器
      网页访问
      元素交互
      截图
    开发工具
      Git 操作
      LSP 集成
      代码审查
    消息平台
      发送消息
      频道管理
      跨平台投递
    记忆与技能
      记忆检索
      技能管理
      会话搜索
    定时任务
      Cron 管理
      任务调度
      投递配置
    媒体处理
      图片生成
      语音转写
      语音合成
    外部服务
      API 调用
      MCP 集成
      数据库操作
```

## 工具防护机制

### 安全检查层次

```mermaid
graph TB
    A[工具调用] --> B[静态检查]
    B --> C[参数验证]
    C --> D[路径安全]
    D --> E[权限检查]
    E --> F[动态检查]
    F --> G[用户审批]
    G --> H[预算检查]
    H --> I[执行]
```

### 安全策略配置

```yaml
# 工具安全配置示例
tools:
  approval:
    # 需要审批的工具
    require_approval_for:
      - terminal
      - file_write
      - delegate
    # 自动批准的模式
    auto_approve_patterns:
      - "ls *"
      - "git status"
  
  # 路径白名单/黑名单
  paths:
    allowed:
      - "~/workspace"
      - "/tmp"
    blocked:
      - "/etc"
      - "~/.ssh"
  
  # 执行限制
  execution:
    timeout_seconds: 300
    max_output_size: "1MB"
    max_memory: "1GB"
```

## MCP 集成流程

Model Context Protocol (MCP) 允许 Hermes 连接外部 MCP 服务器获取更多工具。

```mermaid
sequenceDiagram
    participant Hermes
    participant MCPClient as MCP 客户端
    participant MCPServer as MCP 服务器
    
    Hermes->>MCPClient: 发现 MCP 服务器
    MCPClient->>MCPServer: 连接服务器
    MCPServer-->>MCPClient: 返回工具列表
    MCPClient->>Hermes: 注册 MCP 工具
    
    Note over Hermes,MCPServer: 工具调用时
    Hermes->>MCPClient: 调用 MCP 工具
    MCPClient->>MCPServer: 转发请求
    MCPServer->>MCPServer: 执行工具
    MCPServer-->>MCPClient: 返回结果
    MCPClient-->>Hermes: 返回工具结果
```

## 错误处理与重试

```mermaid
graph TD
    A[工具执行失败] --> B{错误类型}
    B -->|临时错误| C[指数退避重试]
    B -->|参数错误| D[返回错误信息]
    B -->|权限错误| E[拒绝执行]
    B -->|超时| F[终止并清理]
    C --> G{重试次数?}
    G -->|未超限| H[重试执行]
    G -->|超限| I[返回失败]
    H --> J{成功?}
    J -->|是| K[返回结果]
    J -->|否| C
    D --> I
    E --> I
    F --> I
```

## 工具调用示例

### 示例 1：文件读取工具

```mermaid
graph LR
    A[Agent 决定读取文件] --> B[调用 file_read 工具]
    B --> C[参数: path='README.md']
    C --> D[安全检查]
    D --> E{路径在白名单?}
    E -->|是| F[执行读取]
    E -->|否| G[拒绝访问]
    F --> H[返回文件内容]
    H --> I[Agent 处理结果]
```

### 示例 2：终端命令执行

```mermaid
sequenceDiagram
    Agent->>Guard: terminal 命令: 'git status'
    Guard->>Guard: 检查命令白名单
    Guard-->>Agent: 自动批准
    Agent->>Executor: 执行命令
    Executor->>Docker: 启动容器
    Docker->>Docker: 执行 git status
    Docker-->>Executor: 返回输出
    Executor-->>Agent: 返回结果
    Agent->>LLM: 发送结果
```

## 工具调试与监控

```mermaid
graph TB
    A[工具执行] --> B[记录执行日志]
    B --> C[性能指标采集]
    C --> D[错误追踪]
    D --> E[调试信息存储]
    E --> F[可视化仪表板]
```

## 相关文档

- [对话流程](./conversation-flow.md)
- [整体架构](./overview.md)
- [技能系统](./skill-system.md)
- [技术栈](../tech-stack.md)
