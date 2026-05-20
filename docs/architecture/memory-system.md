# 记忆系统架构

本文档详细描述 Hermes Agent 的记忆系统，包括记忆存储、检索、用户建模和跨会话学习的完整机制。

## 记忆系统总览

```mermaid
graph TB
    subgraph Interfaces[接口层]
        MemoryTool[记忆工具]
        SearchAPI[搜索 API]
        UserModel[用户模型 API]
    end
    
    subgraph Core[核心层]
        MemoryManager[MemoryManager<br/>记忆管理器]
        MemoryStore[MemoryStore<br/>记忆存储]
        ContextEngine[ContextEngine<br/>上下文引擎]
        MemoryRetriever[MemoryRetriever<br/>记忆检索器]
    end
    
    subgraph Storage[存储层]
        SQLite[(SQLite 数据库<br/>FTS5 索引)]
        JSONL[(JSONL 文件<br/>会话历史)]
        UserDB[(用户画像 DB)]
        Vector[(向量索引<br/>语义搜索)]
    end
    
    subgraph External[外部集成]
        Honcho[Honcho<br/>辩证式用户建模]
        Mem0[Mem0<br/>记忆层]
    end
    
    Interfaces --> Core
    Core --> Storage
    Core <--> External
```

## 记忆类型

```mermaid
mindmap
  root((记忆类型))
    短期记忆
      当前对话上下文
      工具调用历史
      中间思考过程
    长期记忆
      会话历史摘要
      用户偏好
      学到的事实
    过程记忆
      技能执行记录
      任务完成轨迹
      成功/失败案例
    语义记忆
      实体关系
      事实知识
      概念理解
    用户画像
      交互历史
      偏好模式
      沟通风格
```

## 记忆存储架构

### 存储层次

```mermaid
graph TB
    A[记忆写入] --> B{记忆类型}
    B -->|会话消息| C[JSONL 文件]
    B -->|结构化数据| D[SQLite 数据库]
    B -->|向量嵌入| E[向量索引]
    B -->|用户画像| F[用户 DB]
    
    C --> G[会话历史文件]
    D --> H[FTS5 全文索引]
    E --> I[语义相似度搜索]
    F --> J[用户偏好存储]
```

### 数据库 Schema

```mermaid
erDiagram
    SESSION ||--o{ MESSAGE : contains
    SESSION ||--o{ MEMORY : has
    USER ||--o{ SESSION : has
    USER ||--o{ PREFERENCE : has
    
    SESSION {
        string id PK
        string user_id FK
        string platform
        datetime created_at
        datetime updated_at
        boolean is_archived
        json metadata
    }
    
    MESSAGE {
        string id PK
        string session_id FK
        string role
        string content
        json tool_calls
        json tool_results
        datetime timestamp
        int token_count
    }
    
    MEMORY {
        string id PK
        string session_id FK
        string user_id FK
        string content
        string memory_type
        vector embedding
        float importance
        datetime created_at
        datetime last_accessed
        int access_count
    }
    
    USER {
        string id PK
        string platform
        string platform_user_id
        json preferences
        json interaction_summary
        datetime first_seen
        datetime last_seen
        int total_interactions
    }
    
    PREFERENCE {
        string id PK
        string user_id FK
        string key
        string value
        string source
        datetime discovered_at
        float confidence
    }
```

## 记忆写入流程

```mermaid
sequenceDiagram
    autonumber
    participant Agent as Agent
    participant MemoryMgr as MemoryManager
    participant Store as MemoryStore
    participant Vector as 向量索引
    participant SQLite as SQLite
    
    Agent->>MemoryMgr: 记录交互
    MemoryMgr->>MemoryMgr: 提取关键信息
    
    par 并行存储
        MemoryMgr->>Store: 保存原始消息
        Store->>SQLite: 插入消息记录
        
        MemoryMgr->>MemoryMgr: 生成向量嵌入
        MemoryMgr->>Vector: 存储向量索引
        
        alt 重要记忆
            MemoryMgr->>MemoryMgr: 评估重要性
            MemoryMgr->>Store: 保存长期记忆
        end
        
        alt 检测到用户偏好
            MemoryMgr->>MemoryMgr: 提取偏好
            MemoryMgr->>Store: 更新用户画像
        end
    end
```

## 记忆检索流程

```mermaid
graph TB
    A[记忆查询] --> B[解析查询意图]
    B --> C{检索策略}
    C -->|时间最近| D[按时间排序]
    C -->|语义相似| E[向量相似度搜索]
    C -->|关键词| F[FTS5 全文搜索]
    C -->|混合| G[多策略融合]
    
    D --> H[过滤结果]
    E --> H
    F --> H
    G --> H
    
    H --> I[重排序]
    I --> J[截断到上下文窗口]
    J --> K[格式化为提示词]
    K --> L[返回给 Agent]
```

### 混合检索策略

```mermaid
graph LR
    A[用户查询] --> B[关键词提取]
    A --> C[生成查询向量]
    
    B --> D[FTS5 搜索]
    C --> E[向量相似度搜索]
    
    D --> F[结果集 A]
    E --> G[结果集 B]
    
    F --> H[合并结果]
    G --> H
    
    H --> I[去重]
    I --> J[混合重排序]
    J --> K[Top-K 结果]
```

## 上下文管理

### 上下文构建流程

```mermaid
graph TB
    A[构建上下文] --> B[加载系统提示词]
    B --> C[添加人格设定]
    C --> D[获取相关记忆]
    D --> E[添加用户画像]
    E --> F[加载对话历史]
    F --> G{长度检查}
    G -->|过长| H[压缩历史]
    G -->|合适| I[添加上下文文件]
    H --> I
    I --> J[构建完成]
```

### 上下文压缩

```mermaid
graph LR
    A[原始对话历史] --> B[保留最近 N 轮]
    A --> C[摘要早期消息]
    A --> D[保留系统消息]
    A --> E[保留关键工具调用]
    
    B --> F[合并压缩结果]
    C --> F
    D --> F
    E --> F
    
    F --> G[验证总长度]
    G --> H{仍过长?}
    H -->|是| I[进一步压缩]
    H -->|否| J[完成]
    I --> J
```

## 用户建模系统

### 用户画像维度

```mermaid
graph TB
    A[用户画像] --> B[沟通风格]
    A --> C[技术水平]
    A --> D[兴趣领域]
    A --> E[常用工具]
    A --> F[偏好设置]
    A --> G[交互模式]
    
    B --> H[正式/随意]
    B --> I[简洁/详细]
    
    C --> J[新手/专家]
    
    E --> K[主题偏好]
    
    F --> L[模型偏好]
    F --> M[输出格式偏好]
    F --> N[提醒偏好]
```

### 用户偏好学习

```mermaid
sequenceDiagram
    participant Obs as 观察器
    participant Extract as 提取器
    participant Store as 存储
    participant Validate as 验证器
    
    Obs->>Obs: 监控用户交互
    Obs->>Extract: 检测模式
    Extract->>Extract: 提取候选偏好
    Extract->>Validate: 验证一致性
    Validate->>Validate: 计算置信度
    
    alt 置信度足够高
        Validate->>Store: 保存偏好
        Validate->>Validate: 更新置信度
    end
```

## 记忆重要性评估

```mermaid
graph TB
    A[评估记忆重要性] --> B{内容类型}
    B -->|用户显式声明| C[高重要性]
    B -->|个人信息| C
    B -->|学到的技能| D[中高重要性]
    B -->|普通对话| E[中低重要性]
    B -->|冗余信息| F[低重要性]
    
    C --> G[计算分数]
    D --> G
    E --> G
    F --> G
    
    G --> H[访问频率]
    G --> I[时间衰减]
    G --> J[用户反馈]
    
    H --> K[最终重要性分数]
    I --> K
    J --> K
```

## 记忆老化与遗忘

```mermaid
graph LR
    A[记忆老化系统] --> B[时间衰减]
    A --> C[访问频率]
    A --> D[重要性分数]
    A --> E[相关性]
    
    B --> F[计算衰减因子]
    C --> F
    D --> F
    E --> F
    
    F --> G{保留阈值}
    G -->|高于| H[保留记忆]
    G -->|低于| I[归档/遗忘]
    I --> J[压缩摘要]
    J --> K[存储到长期归档]
```

## 会话搜索

### 搜索接口

```mermaid
graph TB
    A[会话搜索] --> B{搜索类型}
    B -->|关键词| C[FTS5 全文搜索]
    B -->|日期| D[时间范围查询]
    B -->|语义| E[向量相似搜索]
    B -->|组合| F[多条件查询]
    
    C --> G[结果排序]
    D --> G
    E --> G
    F --> G
    
    G --> H[分页显示]
    H --> I[摘要预览]
```

### FTS5 全文搜索

```mermaid
graph LR
    A[FTS5 索引] --> B[消息内容]
    A --> C[工具名称]
    A --> D[文件名]
    A --> E[实体识别]
    
    F[搜索查询] --> G[解析查询语法]
    G --> H[执行搜索]
    H --> I[按 BM25 排序]
    I --> J[返回结果]
```

## 外部集成

### Honcho 集成

```mermaid
sequenceDiagram
    participant Hermes
    participant Honcho
    
    Note over Hermes,Honcho: 会话开始
    Hermes->>Honcho: 创建会话
    Honcho-->>Hermes: 会话 ID
    
    Note over Hermes,Honcho: 交互过程
    Hermes->>Honcho: 添加消息
    Hermes->>Honcho: 添加元数据
    
    Note over Hermes,Honcho: 检索上下文
    Hermes->>Honcho: 获取相关记忆
    Honcho-->>Hermes: 辩证式回忆
```

## 记忆工具

### 可用工具

```mermaid
graph TB
    A[记忆工具] --> B[memory_store]
    A --> C[memory_retrieve]
    A --> D[memory_search]
    A --> E[memory_forget]
    A --> F[memory_summarize]
    
    B --> G[存储新记忆]
    C --> H[检索相关记忆]
    D --> I[搜索历史会话]
    E --> J[删除指定记忆]
    F --> K[生成记忆摘要]
```

## 记忆分析与洞察

```mermaid
graph TB
    A[记忆分析] --> B[使用统计]
    A --> C[模式发现]
    A --> D[趋势分析]
    A --> E[洞察生成]
    
    B --> F[活跃会话数]
    B --> G[记忆增长率]
    
    C --> H[常见任务]
    C --> I[重复模式]
    
    D --> J[兴趣变化]
    D --> K[技能提升]
    
    E --> L[个性化建议]
    E --> M[技能创建提示]
```

## 相关文档

- [整体架构](./overview.md)
- [对话流程](./conversation-flow.md)
- [技能系统](./skill-system.md)
- [技术栈](../tech-stack.md)
