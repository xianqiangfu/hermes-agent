# 可选技能（Optional Skills）

## 概述

可选技能是由 Nous Research 官方维护的技能集合，这些技能**默认不激活**。它们随 Hermes Agent 仓库一起提供，但不会在安装时自动复制到 `~/.hermes/skills/` 目录中。

用户可以通过技能中心浏览、搜索和安装这些可选技能。

## 为什么需要可选技能？

将部分技能设为可选有以下原因：

1. ** niche 集成** - 只对特定用户有用的集成，如特定付费服务、专业工具
2. **实验性功能** - 仍在开发中或尚未经过广泛验证的功能
3. **重量级依赖** - 需要大量额外设置（API 密钥、安装软件等）的技能
4. **保持精简** - 让默认技能集保持精简，同时为有需要的用户提供精选、经过测试的官方技能

## 使用方法

### 浏览可选技能

```bash
# 浏览所有技能（官方技能优先显示）
hermes skills browse

# 只浏览官方可选技能
hermes skills browse --source official
```

### 搜索可选技能

```bash
hermes skills search <关键词>
```

### 安装可选技能

```bash
hermes skills install <技能标识符>
```

安装后，技能会被复制到 `~/.hermes/skills/` 目录并激活，可以立即使用。

## 目录结构

```
optional-skills/
├── 分类目录/
│   ├── DESCRIPTION.md         # 分类描述
│   ├── 技能1/
│   │   ├── SKILL.md           # 技能主文件
│   │   ├── references/        # 参考文档
│   │   ├── templates/         # 模板
│   │   ├── scripts/           # 脚本
│   │   └── assets/            # 资源
│   └── 技能2/
│       └── SKILL.md
└── DESCRIPTION.md             # 可选技能总描述
```

## 可选技能分类

### Blockchain（区块链）

与区块链相关的技能，包括：

- **evm** - EVM 区块链交互
- **hyperliquid** - Hyperliquid DEX 交互
- **solana** - Solana 区块链交互

### Communication（通信）

通信相关技能：

- **one-three-one-rule** - 1-3-1 沟通法则

### Creative（创意）

创意和内容生成相关技能：

- **blender-mcp** - Blender 3D 建模集成
- **concept-diagrams** - 概念图和图表生成
- **hyperframes** - Hyperframes 视频制作
- **kanban-video-orchestrator** - 看板视频编排
- **meme-generation** - 表情包生成

### DevOps（开发运维）

开发运维相关技能：

- **cli** - CLI 开发工具
- **docker-management** - Docker 管理
- **pinggy-tunnel** - Pinggy 隧道
- **watchers** - 文件和服务监控

### Dogfood（内部测试）

内部使用的测试技能：

- **adversarial-ux-test** - 对抗性 UX 测试

### Email（邮件）

邮件相关技能：

- **agentmail** - AgentMail 邮件集成

### Finance（金融）

金融相关技能：

- **3-statement-model** - 三表模型
- **comps-analysis** - 可比公司分析
- **dcf-model** - DCF 估值模型
- **excel-author** - Excel 操作
- **lbo-model** - LBO 模型
- **merger-model** - 并购模型
- **pptx-author** - PowerPoint 操作
- **stocks** - 股票分析

### Health（健康）

健康相关技能：

- **fitness-nutrition** - 健身和营养
- **neuroskill-bci** - NeuroSkill BCI 脑机接口

### MCP（Model Context Protocol）

MCP 相关技能：

- **fastmcp** - FastMCP 服务器开发
- **mcp-devkit** - MCP 开发工具包
- **mcp-server-builder** - MCP 服务器构建

### Research（研究）

研究相关技能：

- **ai-researcher** - AI 研究员助手
- **arxiv-explorer** - arXiv 论文浏览
- **literature-review** - 文献综述
- **research-paper-writing** - 研究论文写作

### Social Media（社交媒体）

社交媒体相关技能：

- **discord** - Discord 机器人
- **linkedin** - LinkedIn 内容创作
- **reddit** - Reddit 助手
- **twitter** - Twitter/X 助手
- **youtube-content** - YouTube 内容创作

### Web（Web 开发）

Web 开发相关技能：

- **frontend-dev** - 前端开发
- **fullstack-dev** - 全栈开发
- **nextjs-developer** - Next.js 开发
- **react-developer** - React 开发
- **web-scraping** - 网页抓取

## 技能安装示例

### 安装区块链技能

```bash
hermes skills install solana
```

### 安装创意技能

```bash
hermes skills install meme-generation
```

### 安装金融技能

```bash
hermes skills install 3-statement-model
```

## 创建自己的可选技能

如果你想为可选技能仓库贡献技能，请遵循以下步骤：

1. 选择合适的分类目录
2. 创建技能目录和 `SKILL.md` 文件
3. 添加必要的支持文件（references、templates、scripts 等）
4. 确保技能包含完整的元数据
5. 测试技能功能正常

### 可选技能元数据建议

除了标准的技能元数据外，可选技能建议包含：

```yaml
---
name: 技能名称
description: 技能描述
version: 1.0.0
author: 作者
license: MIT  # 建议使用 MIT 许可证
metadata:
  hermes:
    tags: [可选, 分类标签]
    category: 分类名称  # 如 blockchain, creative, finance 等
    official: true  # 标记为官方技能
---
```

## 注意事项

### 1. 依赖管理

可选技能可能有额外的依赖，安装时请仔细阅读技能文档中的前置要求。

### 2. API 密钥

许多可选技能需要 API 密钥或其他凭证，请确保在使用前正确配置。

### 3. 平台兼容性

部分可选技能可能只支持特定平台，请检查技能的 `platforms` 字段。

### 4. 更新技能

可选技能会随仓库更新，要获取最新版本：

```bash
# 重新安装技能以获取更新
hermes skills install <技能名> --force
```

## 与核心技能的区别

| 特性 | 核心技能 | 可选技能 |
|------|---------|---------|
| 默认位置 | `~/.hermes/skills/` | `optional-skills/`（仓库中） |
| 默认激活 | 是 | 否 |
| 安装方式 | 安装时自动复制 | 需手动 `hermes skills install` |
| 使用频率 | 高 | 中/低 |
| 依赖复杂度 | 低 | 中/高 |

## 相关资源

- [核心技能系统](../skills/README.md) - 技能系统架构详解
- `tools/skills_hub.py` - 技能中心工具
- `tools/skills_sync.py` - 技能同步工具
