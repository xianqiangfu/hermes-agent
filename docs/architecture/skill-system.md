# 技能系统架构

本文档详细描述 Hermes Agent 的技能系统，包括技能创建、管理、执行和自我改进的完整机制。

## 技能系统总览

```mermaid
graph TB
    subgraph UserInterface[用户界面]
        CLI[CLI /skills 命令]
        Chat[聊天中的 /skill-name]
        Hub[技能中心 Skills Hub]
    end
    
    subgraph Core[技能核心]
        SkillManager[SkillManager<br/>技能管理器]
        SkillLoader[SkillLoader<br/>技能加载器]
        SkillExecutor[SkillExecutor<br/>技能执行器]
        SkillImprover[SkillImprover<br/>技能改进器]
    end
    
    subgraph Storage[存储层]
        SkillDir[~/.hermes/skills/]
        SkillDB[(技能元数据)]
        Provenance[(来源追踪)]
    end
    
    subgraph External[外部集成]
        AgentSkills[agentskills.io]
        Community[社区技能]
        Git[Git 仓库]
    end
    
    UserInterface --> Core
    Core --> Storage
    Core <--> External
```

## 技能结构

### 技能目录结构

```mermaid
graph TB
    A[~/.hermes/skills/] --> B[my-skill/]
    B --> C[skill.yaml]
    B --> D[prompt.md]
    B --> E[README.md]
    B --> F[scripts/]
    F --> G[__init__.py]
    F --> H[helper.py]
    B --> I[tests/]
    I --> J[test_skill.py]
    B --> K[examples/]
    K --> L[example1.md]
```

### 技能定义文件 (skill.yaml)

```mermaid
graph LR
    A[skill.yaml] --> B[name]
    A --> C[version]
    A --> D[description]
    A --> E[author]
    A --> F[category]
    A --> G[tags]
    A --> H[requirements]
    H --> I[dependencies]
    H --> J[env_vars]
    A --> K[commands]
    K --> L[主命令]
    K --> M[子命令]
    A --> N[examples]
    A --> O[config]
```

## 技能生命周期

```mermaid
stateDiagram-v2
    [*] --> DISCOVERED: 发现技能
    DISCOVERED --> LOADING: 开始加载
    LOADING --> VALIDATING: 验证技能
    VALIDATING --> READY: 验证通过
    VALIDATING --> INVALID: 验证失败
    READY --> ACTIVE: 正在执行
    ACTIVE --> READY: 执行完成
    READY --> IMPROVING: 自我改进
    IMPROVING --> READY: 改进完成
    READY --> ARCHIVED: 归档
    INVALID --> [*]
    ARCHIVED --> [*]
```

## 技能创建流程

### 自动技能创建

```mermaid
sequenceDiagram
    autonumber
    participant Agent as Agent
    participant Observer as 任务观察器
    participant Creator as 技能创建器
    participant User as 用户
    
    Note over Agent,User: 检测到可学习的任务
    Agent->>Observer: 记录执行轨迹
    Observer->>Observer: 分析任务模式
    Observer->>Observer: 提取关键步骤
    
    Observer->>Creator: 触发技能创建
    Creator->>Creator: 生成技能大纲
    Creator->>Creator: 编写 prompt.md
    Creator->>Creator: 生成示例
    Creator->>User: 请求确认
    User-->>Creator: 批准/修改
    
    Creator->>Creator: 创建 skill.yaml
    Creator->>Creator: 生成测试
    Creator->>Creator: 保存技能
    
    Creator-->>Agent: 技能创建完成
```

### 手动技能创建

```mermaid
graph TD
    A[用户触发 /create-skill] --> B[收集需求]
    B --> C[生成骨架]
    C --> D[编辑 prompt.md]
    D --> E[编辑 skill.yaml]
    E --> F[添加脚本]
    F --> G[编写示例]
    G --> H[测试技能]
    H --> I{测试通过?}
    I -->|否| J[迭代改进]
    I -->|是| K[保存技能]
    J --> D
    K --> L[注册技能]
```

## 技能加载与发现

```mermaid
graph TB
    A[SkillLoader] --> B[扫描技能目录]
    B --> C[递归遍历子目录]
    C --> D{找到 skill.yaml?}
    D -->|是| E[加载技能定义]
    D -->|否| F[跳过]
    E --> G[验证技能结构]
    G --> H{验证通过?}
    H -->|是| I[加载 prompt.md]
    H -->|否| J[记录错误]
    I --> K[加载脚本]
    K --> L[注册到 SkillManager]
```

### 技能来源

```mermaid
pie title 技能来源
    "内置技能" : 30
    "用户创建" : 40
    "社区分享" : 20
    "Git 仓库" : 10
```

## 技能执行流程

```mermaid
sequenceDiagram
    autonumber
    participant User as 用户
    participant Gateway as 网关
    participant SkillMgr as SkillManager
    participant SkillExec as SkillExecutor
    participant Agent as Agent
    
    User->>Gateway: /skill-name [args]
    Gateway->>SkillMgr: 查找技能
    SkillMgr-->>Gateway: 返回技能定义
    
    Gateway->>SkillExec: 准备执行
    SkillExec->>SkillExec: 解析参数
    SkillExec->>SkillExec: 加载技能提示
    SkillExec->>SkillExec: 添加上下文
    
    SkillExec->>Agent: 注入技能提示
    Agent->>Agent: 执行技能逻辑
    Agent->>Agent: 调用工具(如需要)
    Agent-->>SkillExec: 返回结果
    
    SkillExec-->>Gateway: 返回响应
    Gateway->>User: 发送响应
    
    Note over SkillMgr,Agent: 技能执行后
    SkillMgr->>SkillMgr: 记录使用数据
    SkillMgr->>SkillMgr: 分析执行效果
```

## 技能改进系统

### 改进触发条件

```mermaid
graph LR
    A[技能改进触发] --> B{使用次数}
    A --> C{用户反馈}
    A --> D{执行失败}
    A --> E{定期检查}
    B --> F[达到阈值]
    C --> G[负面反馈]
    D --> H[多次失败]
    E --> I[改进窗口]
    F --> J[启动改进]
    G --> J
    H --> J
    I --> J
```

### 自我改进流程

```mermaid
sequenceDiagram
    participant Improver as SkillImprover
    participant History as 使用历史
    participant Feedback as 用户反馈
    participant LLM as LLM
    participant FS as 文件系统
    
    Improver->>History: 获取执行历史
    Improver->>Feedback: 获取用户反馈
    Improver->>History: 分析失败案例
    
    Improver->>LLM: 生成改进建议
    LLM-->>Improver: 返回改进方案
    
    alt 改进方案有效
        Improver->>FS: 备份原技能
        Improver->>FS: 应用改进
        Improver->>Improver: 测试改进
        alt 测试通过
            Improver->>FS: 保存改进版本
            Improver->>Improver: 更新版本号
        else 测试失败
            Improver->>FS: 回滚到备份
        end
    end
```

## 技能参数与命令

### 命令定义结构

```mermaid
graph TB
    A[CommandDef] --> B[name]
    A --> C[description]
    A --> D[parameters]
    D --> E[ParamDef]
    E --> F[name]
    E --> G[type]
    E --> H[required]
    E --> I[default]
    E --> J[description]
    A --> K[handler]
    A --> L[examples]
```

### 参数类型系统

| 类型 | 说明 | 验证 |
|------|------|------|
| `string` | 字符串 | 长度、正则 |
| `number` | 数字 | 范围 |
| `boolean` | 布尔 | 是/否 |
| `enum` | 枚举 | 选项列表 |
| `path` | 文件路径 | 存在性、权限 |
| `url` | URL | 格式、可达性 |
| `json` | JSON | 格式验证 |

## 技能组合与嵌套

```mermaid
graph TB
    A[主技能] --> B[子技能 1]
    A --> C[子技能 2]
    C --> D[子子技能 A]
    C --> E[子子技能 B]
```

### 技能组合模式

```mermaid
graph LR
    A[顺序执行] --> B[Skill A → Skill B → Skill C]
    D[条件执行] --> E{条件?}
    E -->|是| F[Skill X]
    E -->|否| G[Skill Y]
    H[循环执行] --> I[Skill L × N次]
    J[并行执行] --> K[Skill P & Skill Q]
```

## 技能版本管理

```mermaid
graph TB
    A[技能版本] --> B[语义化版本]
    B --> C[主版本号<br/>不兼容变更]
    B --> D[次版本号<br/>功能新增]
    B --> E[修订号<br/>问题修复]
    
    A --> F[版本历史]
    F --> G[Git 集成]
    F --> H[变更日志]
    F --> I[回滚支持]
```

## 技能元数据与分析

```mermaid
graph TB
    A[SkillAnalytics] --> B[使用统计]
    A --> C[成功率]
    A --> D[平均执行时间]
    A --> E[用户评分]
    A --> F[改进历史]
    
    B --> G[调用次数]
    B --> H[活跃用户]
    B --> I[使用趋势]
    
    C --> J[失败分析]
    C --> K[常见错误]
```

## 技能中心 (Skills Hub)

```mermaid
graph TB
    A[Skills Hub] --> B[技能浏览]
    A --> C[技能搜索]
    A --> D[技能安装]
    A --> E[技能分享]
    A --> F[技能评价]
    
    B --> G[分类浏览]
    B --> H[标签筛选]
    
    C --> I[全文搜索]
    C --> J[语义搜索]
    
    D --> K[依赖管理]
    D --> L[版本选择]
    
    E --> M[发布技能]
    E --> N[更新技能]
```

## 技能安全模型

```mermaid
graph TB
    A[技能安全] --> B[权限隔离]
    A --> C[依赖审计]
    A --> D[代码审查]
    A --> E[沙箱执行]
    
    B --> F[技能权限声明]
    B --> G[用户授权]
    
    C --> H[依赖扫描]
    C --> I[漏洞检查]
    
    D --> J[签名验证]
    D --> K[来源追踪]
```

## 相关文档

- [整体架构](./overview.md)
- [工具调用流程](./tool-call-flow.md)
- [记忆系统](./memory-system.md)
- [技术栈](../tech-stack.md)
