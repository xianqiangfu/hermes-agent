# Hermes Agent - Web UI

基于浏览器的仪表板，用于管理 Hermes Agent 配置、API 密钥和监控活动会话。

## 技术栈

- **构建工具**: Vite
- **框架**: React 19
- **语言**: TypeScript
- **样式**: Tailwind CSS v4（带自定义暗色主题）
- **组件库**: @nous-research/ui（shadcn/ui 风格的组件，无 CLI 依赖）
- **路由**: React Router DOM
- **图标**: Lucide React
- **终端**: xterm.js
- **动画**: GSAP, Motion
- **可视化**: @observablehq/plot, @react-three/fiber, three.js
- **其他**: class-variance-authority, clsx, tailwind-merge

## 快速开始

### 开发模式

```bash
# 1. 启动后端 API 服务器（项目根目录）
cd ../
python -m hermes_cli.main web --no-open

# 2. 在另一个终端启动 Vite 开发服务器（带热模块替换 + API 代理）
cd web/
npm install
npm run dev
```

Vite 开发服务器会将 `/api` 请求代理到 `http://127.0.0.1:9119`（FastAPI 后端）。

### 构建生产版本

```bash
npm run build
```

这会输出到 `../hermes_cli/web_dist/`，FastAPI 服务器将其作为静态 SPA 提供服务。构建的资源通过 `pyproject.toml` 的 package-data 包含在 Python 包中。

## 架构概述

### 目录结构

```
web/
├── public/                 # 静态资源
├── src/
│   ├── components/         # React 组件
│   │   ├── ui/            # 可复用 UI 基元
│   │   ├── *.tsx          # 功能组件
│   ├── contexts/          # React Context 上下文
│   ├── hooks/             # 自定义 Hooks
│   ├── i18n/              # 国际化
│   ├── lib/               # 工具库
│   │   ├── api.ts         # API 客户端 - 所有后端端点的类型化 fetch 包装器
│   │   └── utils.ts       # cn() 辅助函数用于 Tailwind 类合并
│   ├── pages/             # 页面组件
│   │   ├── ChatPage       # 聊天页面
│   │   ├── SessionsPage   # 会话页面 - 代理状态、活动/最近会话
│   │   ├── ConfigPage     # 配置页面 - 动态配置编辑器（从后端读取模式）
│   │   ├── EnvPage        # 环境变量页面 - API 密钥管理（保存/清除）
│   │   ├── ModelsPage     # 模型页面
│   │   ├── AnalyticsPage  # 分析页面
│   │   ├── LogsPage       # 日志页面
│   │   ├── CronPage       # 定时任务页面
│   │   ├── SkillsPage     # 技能页面
│   │   ├── PluginsPage    # 插件页面
│   │   ├── ProfilesPage   # 配置文件页面
│   │   └── DocsPage       # 文档页面
│   ├── plugins/           # 插件系统
│   ├── themes/            # 主题系统
│   ├── App.tsx            # 主布局和导航
│   ├── main.tsx           # React 入口点
│   └── index.css          # Tailwind 导入和主题变量
├── index.html             # HTML 入口
├── vite.config.ts         # Vite 配置
├── tsconfig.json          # TypeScript 配置
├── package.json           # 项目依赖
└── eslint.config.js       # ESLint 配置
```

### 核心页面

| 页面 | 路径 | 功能描述 |
|------|------|----------|
| ChatPage | `/chat` | 交互式聊天界面，内置终端模拟器 |
| SessionsPage | `/sessions` | 会话管理，查看活动和历史会话 |
| ConfigPage | `/config` | 动态配置编辑器，基于后端 JSON Schema |
| EnvPage | `/env` | API 密钥和环境变量管理 |
| ModelsPage | `/models` | 模型配置和选择 |
| AnalyticsPage | `/analytics` | Token 使用分析和成本统计 |
| LogsPage | `/logs` | 系统日志查看 |
| CronPage | `/cron` | 定时任务管理 |
| SkillsPage | `/skills` | 技能库和配置 |
| PluginsPage | `/plugins` | 插件管理 |
| ProfilesPage | `/profiles` | 用户配置文件 |
| DocsPage | `/docs` | 文档查看器 |

## 主要功能

### 1. 响应式仪表板

- 自适应布局，支持移动端和桌面端
- 可折叠侧边栏导航
- 主题切换（亮色/暗色/自定义主题）
- 多语言支持（国际化）

### 2. 聊天界面

- 基于 xterm.js 的终端模拟器
- 实时消息流式传输
- 工具调用可视化
- Markdown 渲染
- 支持附件和图像

### 3. 配置管理

- 动态表单生成（基于 JSON Schema）
- 类型安全的配置编辑
- 实时验证
- 配置文件导入/导出

### 4. 会话管理

- 会话历史查看
- 会话恢复
- 会话搜索和过滤
- 会话详情展示

### 5. 插件系统

- 动态插件加载
- 插件插槽系统
- 插件清单管理
- 可扩展的架构

### 6. 分析和监控

- Token 使用统计
- 成本分析
- 性能监控
- 活动日志

## 核心组件

### App.tsx

主应用组件，负责：

- 路由配置和导航
- 侧边栏布局
- 主题管理
- 插件集成
- 移动端适配
- 聊天页面持久化（当启用嵌入式聊天时）

### 关键 Contexts

| Context | 功能 |
|---------|------|
| `PageHeaderProvider` | 页面头部管理，支持插件标签 |
| `SystemActionsProvider` | 系统操作（重启、更新等） |
| `I18nProvider` | 国际化 |
| `ThemeProvider` | 主题管理 |
| `PluginsProvider` | 插件系统 |

### 插件系统

插件通过清单文件定义，可以：

- 添加新的标签页（`tab.path`）
- 覆盖内置页面（`tab.override`）
- 隐藏标签页（`tab.hidden`）
- 自定义标签页位置（`tab.position`）
- 使用插件插槽在现有 UI 中注入内容

#### 插件插槽

| 插槽名称 | 位置 |
|----------|------|
| `backdrop` | 背景层 |
| `header-banner` | 头部横幅 |
| `header-left` | 头部左侧 |
| `header-right` | 头部右侧 |
| `pre-main` | 主内容区之前 |
| `post-main` | 主内容区之后 |
| `overlay` | 覆盖层 |

### API 客户端 (`src/lib/api.ts`)

提供所有后端端点的类型化访问：

```typescript
// 配置相关
api.getConfig()
api.updateConfig()
api.saveConfig()

// 环境变量相关
api.getEnv()
api.setEnv()
api.deleteEnv()

// 会话相关
api.listSessions()
api.getSession()
api.deleteSession()
api.resumeSession()

// 模型相关
api.listModels()
api.getModel()

// 插件相关
api.getPlugins()

// 系统操作
api.restartGateway()
api.updateHermes()
```

## 主题系统

使用 Tailwind CSS v4 和 CSS 自定义属性实现灵活的主题系统：

```css
/* src/index.css */
:root {
  --component-header-background: ...;
  --component-header-border-image: ...;
  --component-header-clip-path: ...;
  --component-sidebar-background: ...;
  --component-sidebar-clip-path: ...;
  --component-sidebar-border-image: ...;
  --component-tab-clip-path: ...;
  /* 更多自定义属性 */
}
```

支持的主题变体：
- `standard`: 标准布局
- 可通过配置扩展

## 终端集成

聊天页面使用 xterm.js 提供完整的终端体验：

```typescript
// 功能包括：
- 终端模拟器渲染
- 附加组件：
  - fit: 自动调整大小
  - unicode11: Unicode 支持
  - web-links: 链接检测
  - webgl: WebGL 渲染加速
```

## 嵌入式聊天模式

当启用嵌入式聊天时（`window.__HERMES_DASHBOARD_EMBEDDED_CHAT__`）：

- ChatPage 在路由外部持久渲染
- 终端子进程、WebSocket 和 xterm 实例在用户访问其他标签页时保持存活
- 使用 `display:none` 切换隐藏终端而不卸载
- 路由仍然控制 URL，因此 `/chat` 深层链接、浏览器前进/后退和导航高亮仍然有效

## Vite 配置特性

### 开发会话令牌插件

开发模式下的自定义插件：

1. 从运行中的仪表板获取 `index.html`
2. 提取 `window.__HERMES_SESSION_TOKEN__`
3. 将其重新注入到开发 HTML 中
4. 还提取 `window.__HERMES_DASHBOARD_EMBEDDED_CHAT__` 标志

这样可以在开发时无需重新配置即可使用受保护的 API 端点。

### 代理配置

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:9119',
      ws: true
    },
    '/dashboard-plugins': 'http://127.0.0.1:9119'
  }
}
```

### 路径别名

```typescript
resolve: {
  alias: {
    '@': path.resolve(__dirname, './src')
  }
}
```

### 依赖去重

确保共享依赖使用单一副本，避免 hooks 和上下文问题：

```typescript
resolve: {
  dedupe: [
    'react',
    'react-dom',
    '@react-three/fiber',
    '@observablehq/plot',
    'three',
    'leva',
    'gsap'
  ]
}
```

## 国际化 (i18n)

支持多种语言，包括：

- English (`en`)
- 简体中文 (`zh-Hans`)
- 韩语 (`ko`)
- 更多...

翻译键集中管理，组件使用 `useI18n()` hook 访问翻译。

## 开发脚本

| 命令 | 描述 |
|------|------|
| `npm run dev` | 启动开发服务器 |
| `npm run build` | 构建生产版本 |
| `npm run lint` | 运行 ESLint |
| `npm run preview` | 预览生产构建 |

## 环境变量

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `HERMES_DASHBOARD_URL` | 后端 API URL | `http://127.0.0.1:9119` |

## 与后端集成

Web UI 设计为与 FastAPI 后端无缝协作：

1. 后端在 `hermes_cli/web_dist/` 提供静态文件
2. API 端点位于 `/api/*`
3. 身份验证使用会话令牌注入到 `index.html`
4. WebSocket 用于实时更新（聊天、日志等）

## 注意事项

1. **会话令牌**: 在生产环境中，Python 服务器将一次性会话令牌注入到 `index.html`
2. **构建输出**: 构建产物输出到 `../hermes_cli/web_dist/` 以包含在 Python 包中
3. **插件加载**: 插件从 `/api/dashboard/plugins` 异步加载
4. **移动端适配**: 完全响应式设计，包括移动端导航
5. **主题自定义**: 通过 CSS 自定义属性支持深度主题定制

## 相关文档

- [TUI 文档](../ui-tui/README.zh-CN.md)
- [网站文档](../website/README.zh-CN.md)
- [项目主 README](../README.zh-CN.md)
