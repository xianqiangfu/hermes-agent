# 技能系统（Skills System）

## 概述

技能系统是 Hermes Agent 的核心功能之一，它允许通过结构化的 Markdown 文件来扩展 Agent 的能力。每个技能都是一个独立的目录，包含 `SKILL.md` 主文件以及可选的支持文件（如参考资料、模板、脚本等）。

技能系统采用了渐进式披露架构（Progressive Disclosure Architecture），灵感来自 Anthropic 的 Claude Skills 系统：

- **元数据层**：技能名称（≤64字符）、描述（≤1024字符）- 通过 `skills_list` 显示
- **完整指令层**：通过 `skill_view` 按需加载
- **链接文件层**：参考资料、模板等 - 按需加载

## 目录结构

```
skills/
├── 技能分类/              # 可选的分类文件夹
│   ├── 我的技能/          # 技能目录
│   │   ├── SKILL.md       # 主指令文件（必需）
│   │   ├── references/    # 参考文档
│   │   │   ├── api.md
│   │   │   └── examples.md
│   │   ├── templates/     # 输出模板
│   │   │   └── template.md
│   │   ├── scripts/       # 辅助脚本
│   │   │   └── helper.py
│   │   └── assets/        # 其他资源（agentskills.io 标准）
│   └── 另一个技能/
│       └── SKILL.md
└── DESCRIPTION.md         # 分类描述文件
```

### 目录说明

- **`SKILL.md`**：技能的核心文件，包含 YAML 前置元数据和 Markdown 内容
- **`references/`**：参考文档，如 API 文档、示例代码、架构说明等
- **`templates/`**：模板文件，用于生成标准化输出
- **`scripts/`**：可执行脚本，技能可以调用这些脚本来完成特定任务
- **`assets/`**：其他资源文件，如图像、配置文件等
- **`DESCRIPTION.md`**：分类目录的描述文件，说明该分类的用途

## SKILL.md 文件格式

每个技能都必须包含一个 `SKILL.md` 文件，使用 YAML 前置元数据格式，兼容 agentskills.io 标准。

### 基本结构

```markdown
---
name: 技能名称                      # 必需，最多 64 字符
description: 技能的简短描述         # 必需，最多 1024 字符
version: 1.0.0                     # 可选，版本号
license: MIT                       # 可选，许可证
author: 作者名称                   # 可选，作者信息
platforms: [macos, linux]          # 可选，限制支持的操作系统
                                     # 有效值：macos, linux, windows
                                     # 不写则支持所有平台
prerequisites:                     # 可选，运行时要求（旧版）
  env_vars: [API_KEY]             # 环境变量要求
  commands: [curl, jq]            # 命令要求
metadata:                          # 可选，任意键值对（agentskills.io）
  hermes:
    tags: [标签1, 标签2]           # 技能标签
    related_skills: [相关技能]     # 相关技能列表
    config:                        # 技能配置变量声明
      - key: wiki.path
        description: Wiki 目录路径
        default: "~/wiki"
        prompt: Wiki 目录路径
---

# 技能标题

这里是技能的完整内容和说明...

## 使用示例

示例代码和使用说明...
```

### 元数据字段详解

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | 字符串 | 是 | 技能名称，最多 64 字符，用于识别和调用 |
| `description` | 字符串 | 是 | 技能简短描述，最多 1024 字符，在技能列表中显示 |
| `version` | 字符串 | 否 | 技能版本号，建议使用语义化版本 |
| `license` | 字符串 | 否 | 技能许可证，如 MIT, Apache-2.0 等 |
| `author` | 字符串 | 否 | 作者或维护者信息 |
| `platforms` | 数组 | 否 | 支持的平台列表，不写则支持所有平台 |
| `prerequisites` | 对象 | 否 | 运行前提条件（旧版格式） |
| `metadata` | 对象 | 否 | 扩展元数据，可包含自定义字段 |

### metadata.hermes 扩展字段

`metadata.hermes` 是 Hermes 特定的扩展字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `tags` | 数组 | 技能标签，用于分类和搜索 |
| `related_skills` | 数组 | 相关技能名称列表 |
| `requires_toolsets` | 数组 | 需要的工具集 |
| `fallback_for_toolsets` | 数组 | 作为哪些工具集的后备 |
| `requires_tools` | 数组 | 需要的特定工具 |
| `fallback_for_tools` | 数组 | 作为哪些工具的后备 |
| `config` | 数组 | 技能配置变量声明 |

### 配置变量声明

技能可以通过 `metadata.hermes.config` 声明需要的配置变量：

```yaml
metadata:
  hermes:
    config:
      - key: wiki.path
        description: Wiki 知识库目录路径
        default: "~/wiki"
        prompt: Wiki 目录路径
      - key: api.endpoint
        description: API 服务端点
        default: "https://api.example.com"
```

这些配置值存储在 `~/.hermes/config.yaml` 的 `skills.config` 下，技能加载时会自动注入。

## 技能学习机制

### 技能发现

Hermes 从以下位置发现和加载技能：

1. **本地技能目录**：`~/.hermes/skills/` - 用户个人技能
2. **外部技能目录**：通过 `config.yaml` 中的 `skills.external_dirs` 配置
3. **项目内置技能**：`skills/` 目录（本仓库）

### 技能加载流程

1. **扫描目录**：遍历所有技能目录，查找 `SKILL.md` 文件
2. **解析元数据**：读取 YAML 前置元数据
3. **平台过滤**：跳过不支持当前平台的技能
4. **禁用过滤**：跳过用户在配置中禁用的技能
5. **缓存命令**：生成 `/技能名` 斜杠命令映射

### 技能调用方式

技能可以通过多种方式调用：

#### 1. 斜杠命令（推荐）

```
/技能名称 用户指令
```

示例：
```
/claude-code 重构 auth 模块
```

#### 2. 自然语言调用

Agent 可以根据用户的自然语言请求自动识别和加载合适的技能。

#### 3. 预加载技能

启动 CLI 时通过 `-s` 参数预加载技能：

```bash
hermes -s claude-code -s test-driven-development
```

#### 4. 技能包（Skill Bundles）

通过技能包一次性加载多个技能：

```
/backend-dev 开始开发新功能
```

## 技能存储机制

### 技能位置

- **用户技能**：`~/.hermes/skills/` - 用户安装和创建的技能
- **技能包**：`~/.hermes/skill-bundles/` - 技能包定义文件
- **配置文件**：`~/.hermes/config.yaml` - 技能系统配置

### 技能同步

技能可以通过 `skills_tool` 进行同步、安装和管理：

```bash
hermes skills browse              # 浏览技能中心
hermes skills install <技能名>    # 安装技能
hermes skills sync                # 同步技能
```

## 核心功能

### 1. 渐进式披露

技能系统采用三层披露机制，优化 token 使用效率：

- **第一层**：`skills_list` - 只返回元数据（名称、描述）
- **第二层**：`skill_view(技能名)` - 返回完整指令
- **第三层**：`skill_view(技能名, 文件路径)` - 返回链接文件

### 2. 模板变量替换

技能内容支持模板变量替换：

- `${HERMES_SKILL_DIR}` - 技能目录的绝对路径
- `${HERMES_SESSION_ID}` - 当前会话 ID

这些变量在技能加载时自动替换为实际值。

### 3. 内联 Shell 执行

技能可以包含内联 Shell 命令（需在配置中启用）：

```markdown
当前日期：!`date +%Y-%m-%d`
```

命令在技能加载时执行，输出替换到内容中。

### 4. 配置注入

声明了配置变量的技能，加载时会自动注入当前配置值：

```
[Skill config (from ~/.hermes/config.yaml):
  wiki.path = /home/user/wiki
  api.endpoint = https://api.example.com
]
```

### 5. 支持文件自动发现

技能目录中的 `references/`、`templates/`、`scripts/`、`assets/` 子目录会被自动发现，并在技能加载时提示 Agent 可以使用这些文件。

## 使用示例

### 创建一个新技能

1. 创建技能目录：

```bash
mkdir -p ~/.hermes/skills/my-skill
```

2. 创建 `SKILL.md` 文件：

```markdown
---
name: my-skill
description: 我的示例技能，演示如何使用技能系统
version: 1.0.0
author: Your Name
tags: [示例, 教程]
---

# 我的示例技能

这是一个示例技能，用于演示技能系统的功能。

## 使用方法

1. 第一步...
2. 第二步...
3. 第三步...

## 示例

```
示例代码
```
```

3. （可选）添加支持文件：

```bash
mkdir -p ~/.hermes/skills/my-skill/templates
mkdir -p ~/.hermes/skills/my-skill/scripts
```

### 使用技能

在 Hermes 会话中：

```
/my-skill 请帮我完成一个任务
```

### 技能包示例

创建技能包文件 `~/.hermes/skill-bundles/backend-dev.yaml`：

```yaml
name: backend-dev
description: 后端开发技能包 - 代码审查、测试、PR 工作流
skills:
  - github-code-review
  - test-driven-development
  - github-pr-workflow
instruction: |
  作为后端开发专家，遵循最佳实践完成任务。
```

使用技能包：

```
/backend-dev 开始开发新的 API 端点
```

## 核心工具

技能系统提供以下核心工具（在 `tools.skills_tool` 中）：

### `skills_list()`

列出所有可用技能的元数据。

```python
from tools.skills_tool import skills_list

result = skills_list()
# 返回所有技能的名称、描述等元数据
```

### `skill_view(name, file_path=None, task_id=None, preprocess=True)`

查看技能的完整内容或特定文件。

```python
from tools.skills_tool import skill_view

# 查看技能主文件
content = skill_view("claude-code")

# 查看技能中的参考文件
content = skill_view("claude-code", "references/api.md")
```

### 其他技能相关工具

- `skills_hub` - 技能中心，浏览和安装技能
- `skills_sync` - 技能同步
- `skill_manager_tool` - 技能管理
- `skill_usage` - 技能使用统计

## 核心模块

技能系统的核心代码位于以下模块：

| 模块 | 功能 |
|------|------|
| `agent.skill_utils` | 技能元数据工具、前置解析、平台匹配 |
| `agent.skill_commands` | 斜杠命令处理、技能调用消息构建 |
| `agent.skill_bundles` | 技能包功能 |
| `agent.skill_preprocessing` | 技能内容预处理（模板替换、内联 Shell） |
| `tools.skills_tool` | 技能列表和查看工具 |
| `tools.skills_hub` | 技能中心 |
| `tools.skills_sync` | 技能同步 |

## 注意事项

### 1. 技能安全

- 技能可以执行 Shell 命令（如果启用），请只安装可信来源的技能
- 内联 Shell 功能默认禁用，需在 `config.yaml` 中启用 `skills.inline_shell`
- 技能加载时会进行提示注入检测

### 2. 平台兼容性

- 使用 `platforms` 字段限制技能支持的操作系统
- 常见值：`[macos, linux, windows]`
- 不指定则支持所有平台

### 3. Token 效率

- 技能列表只返回元数据，节省 token
- 使用 `skill_view` 按需加载完整技能内容
- 大技能可以拆分到 `references/` 目录中，按需引用

### 4. 技能禁用

可以在 `config.yaml` 中禁用特定技能：

```yaml
skills:
  disabled:
    - 不需要的技能1
    - 不需要的技能2
  platform_disabled:
    telegram:
      - 某些技能
```

### 5. 外部技能目录

可以配置外部技能目录：

```yaml
skills:
  external_dirs:
    - ~/my-skills
    - /path/to/shared/skills
```

## 配置选项

技能系统在 `config.yaml` 中的配置：

```yaml
skills:
  # 禁用的技能列表
  disabled: []
  
  # 平台特定禁用的技能
  platform_disabled: {}
  
  # 外部技能目录
  external_dirs: []
  
  # 启用模板变量替换（默认 true）
  template_vars: true
  
  # 启用内联 Shell 执行（默认 false）
  inline_shell: false
  
  # 内联 Shell 超时时间（秒，默认 10）
  inline_shell_timeout: 10
  
  # 技能配置值
  config:
    技能名:
      配置键: 配置值
```

## 更多资源

- [可选技能（Optional Skills）](../optional-skills/README.md) - 可选技能的详细说明
- 技能系统代码：
  - `agent/skill_utils.py` - 技能工具函数
  - `agent/skill_commands.py` - 斜杠命令处理
  - `agent/skill_bundles.py` - 技能包
  - `agent/skill_preprocessing.py` - 内容预处理
  - `tools/skills_tool.py` - 技能工具
