# 定时任务流程

本文档详细描述 Hermes Agent 的定时任务系统，包括任务调度、执行、消息投递的完整机制。

## 定时系统总览

```mermaid
graph TB
    subgraph UserInterface[用户界面]
        CronCmd[CLI /cron 命令]
        ChatCmd[聊天中的 /cron]
        ConfigFile[配置文件 ~/.hermes/cron.yaml]
    end
    
    subgraph Core[核心系统]
        CronScheduler[CronScheduler<br/>任务调度器]
        JobManager[JobManager<br/>任务管理器]
        JobExecutor[JobExecutor<br/>任务执行器]
        DeliveryRouter[DeliveryRouter<br/>投递路由器]
    end
    
    subgraph Storage[存储层]
        JobDB[(任务数据库)]
        JobLog[(执行日志)]
        Output[(输出文件)]
    end
    
    subgraph Platforms[消息平台]
        Telegram[Telegram]
        Discord[Discord]
        Slack[Slack]
        Local[本地]
    end
    
    UserInterface --> Core
    Core --> Storage
    Core --> Platforms
```

## Cron 表达式解析

```mermaid
graph TB
    A[Cron 表达式] --> B[解析器]
    B --> C{格式类型}
    C -->|标准| D[5 字段]
    C -->|扩展| E[6-7 字段]
    C -->|自然语言| F[解析为标准]
    
    D --> G[字段解析]
    E --> G
    F --> G
    
    G --> H[分钟]
    G --> I[小时]
    G --> J[日期]
    G --> K[月份]
    G --> L[星期]
    G --> M[年份]
    
    H --> N[生成调度表]
    I --> N
    J --> N
    K --> N
    L --> N
    M --> N
```

### Cron 字段说明

| 字段 | 范围 | 特殊字符 | 示例 |
|------|------|----------|------|
| 分钟 | 0-59 | `*` `,` `-` `/` | `*/5` 每 5 分钟 |
| 小时 | 0-23 | `*` `,` `-` `/` | `9-17` 早 9 晚 5 |
| 日期 | 1-31 | `*` `,` `-` `/` `?` `L` `W` | `15` 每月 15 号 |
| 月份 | 1-12 | `*` `,` `-` `/` | `1,3,5` 1/3/5 月 |
| 星期 | 0-6 (日-六) | `*` `,` `-` `/` `?` `L` `#` | `1-5` 工作日 |
| 年份 (可选) | 2024-2100 | `*` `,` `-` `/` | `2024/2` 偶数年 |

## 任务定义结构

```mermaid
graph TB
    A[CronJob] --> B[id]
    A --> C[name]
    A --> D[description]
    A --> E[schedule]
    A --> F[action]
    A --> G[delivery]
    A --> H[enabled]
    A --> I[timezone]
    A --> J[metadata]
    
    F --> K{动作类型}
    K -->|prompt| L[LLM 提示词]
    K -->|skill| M[技能名称+参数]
    K -->|command| N[Shell 命令]
    K -->|python| O[Python 脚本]
    
    G --> P[投递目标列表]
    P --> Q[origin]
    P --> R[local]
    P --> S[平台]
    P --> T[平台:聊天]
```

## 任务调度流程

```mermaid
sequenceDiagram
    autonumber
    participant Scheduler as CronScheduler
    participant JobStore as JobStore
    participant Timer as 定时器
    participant Executor as JobExecutor
    
    Scheduler->>JobStore: 加载任务
    JobStore-->>Scheduler: 任务列表
    
    loop 每个任务
        Scheduler->>Scheduler: 解析 cron 表达式
        Scheduler->>Scheduler: 计算下次执行时间
    end
    
    Scheduler->>Timer: 启动调度循环
    
    loop 每秒检查
        Timer->>Timer: 获取当前时间
        Timer->>Scheduler: 检查到期任务
        
        alt 任务到期
            Scheduler->>Executor: 提交执行
            Executor->>Executor: 异步执行
            Scheduler->>Scheduler: 计算下次执行时间
        end
    end
```

## 任务执行流程

```mermaid
sequenceDiagram
    autonumber
    participant Executor as JobExecutor
    participant Action as 动作执行
    participant Agent as Agent
    participant Router as DeliveryRouter
    participant Log as 任务日志
    
    Executor->>Executor: 准备执行环境
    Executor->>Log: 记录开始时间
    
    alt 提示词类型
        Executor->>Agent: 发送提示词
        Agent->>Agent: 处理提示词
        Agent->>Agent: 调用工具(如需要)
        Agent-->>Executor: 返回响应
    else 技能类型
        Executor->>Action: 执行技能
        Action-->>Executor: 返回结果
    else 命令类型
        Executor->>Action: 执行 Shell 命令
        Action-->>Executor: 返回输出
    else 脚本类型
        Executor->>Action: 执行 Python 脚本
        Action-->>Executor: 返回结果
    end
    
    Executor->>Log: 记录执行结果
    
    Executor->>Router: 投递结果
    Router->>Router: 解析投递目标
    Router->>Router: 发送到各目标
    
    Executor->>Log: 记录投递状态
```

## 消息投递流程

```mermaid
graph TB
    A[投递任务输出] --> B[解析投递目标]
    B --> C{目标类型}
    C -->|origin| D[返回来源]
    C -->|local| E[保存本地文件]
    C -->|platform| F[发送到主频道]
    C -->|platform:chat_id| G[发送到指定聊天]
    C -->|platform:chat:thread| H[发送到指定线程]
    
    D --> I[获取源平台]
    E --> J[写入 ~/.hermes/cron/output/]
    F --> K[获取主频道配置]
    G --> L[直接投递]
    H --> L
    
    I --> M[发送消息]
    K --> M
    L --> M
    
    M --> N{消息过长?}
    N -->|是| O[截断并保存完整内容]
    N -->|否| P[发送完整消息]
    O --> P
```

## 任务管理操作

```mermaid
graph TB
    A[任务管理] --> B[创建任务]
    A --> C[列出任务]
    A --> D[编辑任务]
    A --> E[删除任务]
    A --> F[启用/禁用]
    A --> G[立即执行]
    A --> H[查看日志]
    
    B --> I[验证 cron]
    I --> J[保存任务]
    
    C --> K[筛选/排序]
    K --> L[显示状态]
    
    E --> M[确认删除]
    M --> N[归档日志]
    
    G --> O[跳过调度检查]
    O --> P[立即执行]
```

## 任务状态机

```mermaid
stateDiagram-v2
    [*] --> INACTIVE: 新创建
    INACTIVE --> ACTIVE: 启用
    ACTIVE --> ACTIVE: 执行中
    ACTIVE --> PAUSED: 禁用
    PAUSED --> ACTIVE: 重新启用
    ACTIVE --> FAILED: 执行失败
    FAILED --> ACTIVE: 重试
    ACTIVE --> COMPLETED: 执行成功
    COMPLETED --> ACTIVE: 等待下次
    INACTIVE --> ARCHIVED: 删除
    PAUSED --> ARCHIVED: 删除
    ARCHIVED --> [*]
```

## 任务配置示例

### 配置文件格式 (cron.yaml)

```mermaid
graph TB
    A[cron.yaml] --> B[jobs]
    B --> C[job1]
    B --> D[job2]
    
    C --> E[name: 日报]
    C --> F[schedule: '0 9 * * 1-5']
    C --> G[action]
    G --> H[type: prompt]
    G --> I[content: '生成今日工作摘要...']
    C --> J[delivery]
    J --> K['telegram:123456']
    C --> L[enabled: true]
```

### 常见任务示例

| 任务类型 | Cron 表达式 | 说明 |
|----------|-------------|------|
| 日报 | `0 9 * * 1-5` | 工作日早 9 点 |
| 周报 | `0 10 * * 1` | 周一早 10 点 |
| 备份 | `0 2 * * *` | 每天凌晨 2 点 |
| 健康检查 | `*/30 * * * *` | 每 30 分钟 |
| 月度报告 | `0 8 1 * *` | 每月 1 号早 8 点 |

## 时区处理

```mermaid
graph TB
    A[时区配置] --> B{配置位置}
    B -->|任务级| C[任务 timezone 字段]
    B -->|全局| D[~/.hermes/config.yaml]
    B -->|系统| E[系统时区]
    
    C --> F[优先使用任务时区]
    D --> G[其次全局时区]
    E --> H[最后系统时区]
    
    F --> I[计算执行时间]
    G --> I
    H --> I
```

## 任务执行日志

```mermaid
graph TB
    A[任务日志] --> B[执行历史]
    A --> C[输出内容]
    A --> D[错误信息]
    A --> E[投递状态]
    
    B --> F[开始时间]
    B --> G[结束时间]
    B --> H[执行时长]
    B --> I[状态]
    
    E --> J[目标列表]
    E --> K[成功/失败]
    E --> L[消息 ID]
```

## 错误处理与重试

```mermaid
graph TB
    A[任务执行失败] --> B{错误类型}
    B -->|临时错误| C[指数退避重试]
    B -->|配置错误| D[禁用任务]
    B -->|平台错误| E[重试投递]
    B -->|超时| F[终止并清理]
    
    C --> G{重试次数?}
    G -->|未超限| H[等待后重试]
    G -->|超限| I[禁用+通知]
    H --> J{成功?}
    J -->|是| K[重置失败计数]
    J -->|否| C
    E --> L{重试次数?}
    L -->|未超限| M[重试投递]
    L -->|超限| N[记录失败]
    M --> O{成功?}
    O -->|是| P[继续]
    O -->|否| L
```

## 任务监控与通知

```mermaid
graph TB
    A[任务监控] --> B[执行统计]
    A --> C[失败告警]
    A --> D[状态通知]
    
    B --> E[成功率]
    B --> F[平均执行时间]
    B --> G[下次执行]
    
    C --> H{失败次数?}
    H -->|>阈值| I[发送告警]
    
    D --> J[任务执行通知]
    D --> K[任务禁用通知]
```

## CLI 命令示例

```mermaid
graph TB
    A[hermes cron] --> B[list]
    A --> C[create]
    A --> D[edit]
    A --> E[delete]
    A --> F[enable]
    A --> G[disable]
    A --> H[run]
    A --> I[logs]
    
    C --> J[--schedule]
    C --> K[--action]
    C --> L[--delivery]
    
    H --> M[--now]
    H --> N[--job-id]
    
    I --> O[--tail]
    I --> P[--follow]
```

## 相关文档

- [整体架构](./overview.md)
- [网关架构](./gateway-architecture.md)
- [对话流程](./conversation-flow.md)
- [技术栈](../tech-stack.md)
