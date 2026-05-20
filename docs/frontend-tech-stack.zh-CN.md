# Hermes Agent 前端技术栈分析

本文档详细分析 Hermes Agent 项目中三个前端模块（ui-tui、web、website）的技术栈选择、架构设计和最佳实践。

## 目录

- [整体架构概览](#整体架构概览)
- [UI-TUI 模块技术栈](#ui-tui-模块技术栈)
- [Web 模块技术栈](#web-模块技术栈)
- [Website 模块技术栈](#website-模块技术栈)
- [技术栈对比与分析](#技术栈对比与分析)
- [最佳实践与设计模式](#最佳实践与设计模式)
- [依赖关系图](#依赖关系图)

---

## 整体架构概览

### 三个前端模块的定位

| 模块 | 技术栈核心 | 主要用途 | 运行环境 |
|------|------------|----------|----------|
| **ui-tui** | React + Ink + TypeScript | 终端用户界面 | 终端/TTY |
| **web** | React 19 + Vite + Tailwind | Web 仪表板 | 浏览器 |
| **website** | Docusaurus 3.x | 文档网站 | 浏览器 |

### 共享技术基础

尽管三个模块针对不同环境，但它们共享一些核心技术选择：

- **TypeScript**: 所有模块都使用 TypeScript 进行类型安全
- **React**: 所有模块都基于 React（或 React 生态系统）
- **Node.js 工具链**: 构建、开发、测试工具基于 Node.js
- **现代 JavaScript**: 使用 ES Module (`.mjs`)，CommonJS 较少

---

## UI-TUI 模块技术栈

### 核心框架

#### React 19.x
- 用于构建组件化 UI
- 利用最新的 React 特性（Concurrent Mode、Suspense 等）
- 与 Ink 配合实现终端渲染

#### Ink 6.8.0
```json
"ink": "^6.8.0"
```
- 基于 React 的终端渲染器
- 允许使用 React 组件模型构建终端 UI
- 提供 Flexbox 布局、文本样式、键盘输入处理等功能
- **Fork**: 项目包含自定义分支 `@hermes/ink`，进行了定制修改

#### 自定义 Ink 分支 (`packages/hermes-ink`)
```json
"@hermes/ink": "file:./packages/hermes-ink"
```
- 本地依赖的 Ink 修改版
- 可能包含性能优化、功能扩展或特定修复
- 使用内部 API 进行深度集成

### 状态管理

#### Nanostores
```json
"nanostores": "^1.2.0",
"@nanostores/react": "^1.1.0"
```
- **轻量级状态管理**: 极小的 bundle size
- **原子化设计**: 基于原子的状态存储
- **框架无关**: 核心库不依赖 React
- **响应式更新**: 自动跟踪依赖和重新渲染
- **在项目中的使用**:
  - `overlayStore.ts`: 管理覆盖层状态
  - `uiStore.ts`: 管理 UI 标志
  - `delegationStore.ts`: 委托状态
  - `spawnHistoryStore.ts`: 生成历史
  - `fpsStore.ts`: FPS 追踪

### 构建工具

#### esbuild
```json
"esbuild": "~0.27.0"
```
- 极快的 JavaScript/TypeScript 打包器
- 使用 Go 编写，性能优异
- 在 `scripts/build.mjs` 中配置和使用

#### TypeScript 5.7.x
```json
"typescript": "^5.7.0"
```
- 严格类型检查
- 现代 TypeScript 特性
- 配置文件: `tsconfig.json`, `tsconfig.build.json`

#### tsx
```json
"tsx": "^4.19.0"
```
- Node.js 的 TypeScript 执行器
- 无需预编译即可运行 `.ts` 和 `.tsx` 文件
- 用于 `npm start` 和 `npm run dev`

### 代码质量

#### ESLint 9.x
```json
"eslint": "^9",
"@eslint/js": "^9",
"@typescript-eslint/eslint-plugin": "^8",
"@typescript-eslint/parser": "^8",
"eslint-plugin-react": "^7",
"eslint-plugin-react-hooks": "^7",
"eslint-plugin-react-compiler": "^19.1.0-rc.2",
"eslint-plugin-perfectionist": "^5",
"eslint-plugin-unused-imports": "^4"
```
- 扁平化配置 (`eslint.config.mjs`)
- React 特定规则
- React Compiler 支持
- 代码风格统一 (perfectionist)
- 未使用导入自动清理

#### Prettier 3.x
```json
"prettier": "^3"
```
- 代码格式化
- 配置: `.prettierrc`

#### Babel (可选)
```json
"@babel/cli": "^7.28.6",
"@babel/core": "^7.29.0",
"@babel/plugin-syntax-jsx": "^7.28.6"
```
- 主要用于 React Compiler
- JSX 语法支持

### React Compiler
```json
"babel-plugin-react-compiler": "^1.0.0"
```
- React 的官方编译优化
- 自动 memoization
- 减少手动优化需求
- 显著提升渲染性能

### 测试框架

#### Vitest 4.1.3
```json
"vitest": "^4.1.3"
```
- 基于 Vite 的测试运行器
- Jest 兼容 API
- 极快的执行速度
- 配置: `vitest.config.ts`

### 输入处理

#### ink-text-input 6.0.0
```json
"ink-text-input": "^6.0.0"
```
- Ink 的文本输入组件
- 支持光标移动、选择、历史记录等
- 在提示流程中使用（sudo、secret 等）

### 其他工具

#### unicode-animations
```json
"unicode-animations": "^1.0.3"
```
- Unicode 动画支持
- 终端中的加载动画、进度指示器等

### 架构特点

#### 进程间通信 (IPC)
- **JSON-RPC 2.0**: 标准化的 RPC 协议
- **Transport 层**: 支持两种模式
  1. **Spawn 模式**: 通过 stdio 与 Python 子进程通信
  2. **Attach 模式**: 通过 WebSocket 连接到已运行的网关
- **GatewayClient**: 完整的客户端实现，包括:
  - 请求超时管理
  - 事件缓冲
  - 日志环形缓冲
  - 自动重连

#### 自定义组件库
项目包含多个 Ink 自定义组件：
- `textInput.tsx`: 增强的文本输入（非 ink-text-input）
- `markdown.tsx`: Markdown 渲染器
- `messageLine.tsx`: 消息行显示
- `thinking.tsx`: 思考/工具活动指示器
- `prompts.tsx`: 各种提示流程
- 等等

#### 事件驱动架构
```typescript
// GatewayClient 继承 EventEmitter
export class GatewayClient extends EventEmitter {
  // 事件: 'event', 'exit'
  // 方法: request(), drain(), kill()
}
```

#### 自定义 Hooks
```typescript
useCompletion()      // Tab 补全
useInputHistory()    // 输入历史
useQueue()           // 消息队列
useVirtualHistory()  // 虚拟历史
useComposerState()   // 编辑器状态
useInputHandlers()   // 输入处理
useTurnState()       // 轮次状态
useMainApp()         // 主应用
useSessionLifecycle() // 会话生命周期
useSubmission()      // 提交处理
useLongRunToolCharms() // 长期运行工具提示
useConfigSync()      // 配置同步
```

### UI-TUI 模块文件依赖树

```
ui-tui/
├── src/
│   ├── entry.tsx (入口)
│   │   ├── GatewayClient (gatewayClient.ts)
│   │   └── App (app.tsx)
│   │
│   ├── app.tsx (主应用)
│   │   ├── useMainApp()
│   │   ├── gatewayContext.tsx
│   │   ├── app/layout 组件
│   │   └── app/ 逻辑
│   │
│   ├── app/ (核心逻辑)
│   │   ├── createGatewayEventHandler.ts
│   │   ├── createSlashHandler.ts
│   │   ├── useComposerState.ts
│   │   ├── useInputHandlers.ts
│   │   ├── useTurnState.ts
│   │   ├── useMainApp.ts
│   │   ├── useSessionLifecycle.ts
│   │   ├── useSubmission.ts
│   │   ├── useConfigSync.ts
│   │   ├── useLongRunToolCharms.ts
│   │   ├── overlayStore.ts
│   │   ├── uiStore.ts
│   │   ├── delegationStore.ts
│   │   ├── spawnHistoryStore.ts
│   │   ├── scroll.ts
│   │   ├── setupHandoff.ts
│   │   ├── turnController.ts
│   │   ├── turnStore.ts
│   │   ├── slash/ (斜杠命令)
│   │   │   ├── registry.ts
│   │   │   ├── types.ts
│   │   │   └── commands/
│   │   │       ├── core.ts
│   │   │       ├── debug.ts
│   │   │       ├── ops.ts
│   │   │       ├── session.ts
│   │   │       └── setup.ts
│   │   ├── constants.ts
│   │   ├── helpers.ts
│   │   └── interfaces.ts
│   │
│   ├── components/ (UI 组件)
│   │   ├── appChrome.tsx
│   │   ├── appLayout.tsx
│   │   ├── appOverlays.tsx
│   │   ├── branding.tsx
│   │   ├── markdown.tsx
│   │   ├── maskedPrompt.tsx
│   │   ├── messageLine.tsx
│   │   ├── modelPicker.tsx
│   │   ├── prompts.tsx
│   │   ├── queuedMessages.tsx
│   │   ├── sessionPicker.tsx
│   │   ├── textInput.tsx
│   │   ├── thinking.tsx
│   │   └── agentsOverlay.tsx
│   │
│   ├── hooks/ (自定义 Hooks)
│   │   ├── useCompletion.ts
│   │   ├── useInputHistory.ts
│   │   ├── useQueue.ts
│   │   └── useVirtualHistory.ts
│   │
│   ├── lib/ (工具库)
│   │   ├── history.ts
│   │   ├── messages.ts
│   │   ├── osc52.ts
│   │   ├── rpc.ts
│   │   ├── text.ts
│   │   ├── gracefulExit.ts
│   │   ├── memory.ts
│   │   ├── memoryMonitor.ts
│   │   ├── terminalModes.ts
│   │   ├── perfPane.ts
│   │   ├── fpsStore.ts
│   │   └── forceTruecolor.ts
│   │
│   ├── gatewayClient.ts (核心通信)
│   │   ├── JSON-RPC 实现
│   │   ├── 子进程管理
│   │   └── WebSocket 支持
│   │
│   ├── theme.ts (主题系统)
│   ├── banner.ts (ASCII art)
│   ├── constants.ts (常量)
│   └── types.ts (类型定义)
│
├── packages/hermes-ink/ (自定义 Ink)
├── scripts/build.mjs (构建脚本)
└── 配置文件
    ├── tsconfig.json
    ├── tsconfig.build.json
    ├── eslint.config.mjs
    ├── vitest.config.ts
    └── .prettierrc
```

---

## Web 模块技术栈

### 核心框架

#### React 19.2.4
```json
"react": "^19.2.4",
"react-dom": "^19.2.4"
```
- 最新的 React 主要版本
- 利用新特性如 Transitions、Suspense 改进
- 更好的并发渲染支持

#### React Router DOM 7.14.1
```json
"react-router-dom": "^7.14.1"
```
- 现代版本的 React Router
- 数据加载 API
- 嵌套路由
- 导航状态管理
- 动态路由匹配

### 构建工具

#### Vite 7.3.1
```json
"vite": "^7.3.1",
"@vitejs/plugin-react": "^5.2.0"
```
- **极快的开发服务器**: 基于 ESM 的 HMR
- **优化的生产构建**: Rollup 打包
- **丰富的插件生态系统**
- **自定义插件**:
  ```typescript
  // vite.config.ts 中的自定义插件
  function hermesDevToken() {
    // 从后端获取会话令牌并注入到 HTML 中
  }
  ```
- **代理配置**: `/api` → `http://127.0.0.1:9119`
- **路径别名**: `@` → `./src`
- **依赖去重**: 避免多个 React 副本

#### TypeScript ~5.9.3
```json
"typescript": "~5.9.3"
```
- 最新稳定的 TypeScript
- 配置文件:
  - `tsconfig.json`: 根配置
  - `tsconfig.node.json`: Node.js 环境配置
  - `tsconfig.app.json`: 应用配置

### 样式系统

#### Tailwind CSS v4.2.1
```json
"tailwindcss": "^4.2.1",
"@tailwindcss/vite": "^4.2.1"
```
- **v4 版本**: 最新的 Tailwind 主要版本
- **Utility-First CSS**: 原子化 CSS 方法
- **Vite 集成**: 原生 Vite 插件
- **自定义主题**: CSS 自定义属性
- **配置**: 无配置文件（或使用 CSS 配置）

#### class-variance-authority 0.7.1
```json
"class-variance-authority": "^0.7.1"
```
- **CVA**: 创建类型安全的可变组件
- 与 shadcn/ui 风格配合使用
- 变体定义、默认值、复合变体

#### clsx 2.1.1 & tailwind-merge 3.5.0
```json
"clsx": "^2.1.1",
"tailwind-merge": "^3.5.0"
```
- **clsx**: 条件类名构建
- **tailwind-merge**: 智能合并 Tailwind 类
- **cn() 函数**: 两者结合的实用工具
  ```typescript
  // lib/utils.ts
  import { clsx, type ClassValue } from 'clsx'
  import { twMerge } from 'tailwind-merge'
  
  export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
  }
  ```

### UI 组件库

#### @nous-research/ui ^0.14.2
```json
"@nous-research/ui": "^0.14.2"
```
- Nous Research 的内部 UI 组件库
- shadcn/ui 风格（无 CLI 依赖）
- 可复用的设计系统
- 包含组件:
  - Button
  - ListItem
  - SelectionSwitcher
  - Spinner
  - 等等

### 图标系统

#### lucide-react ^0.577.0
```json
"lucide-react": "^0.577.0"
```
- 现代化的 SVG 图标库
- 树摇友好
- 统一的图标风格
- 在项目中大量使用

### 终端模拟器

#### xterm.js 6.0.0
```json
"@xterm/xterm": "^6.0.0",
"@xterm/addon-fit": "^0.11.0",
"@xterm/addon-unicode11": "^0.9.0",
"@xterm/addon-web-links": "^0.12.0",
"@xterm/addon-webgl": "^0.19.0"
```
- **Web 终端模拟器**: 功能完整的终端
- **Add-ons**:
  - `fit`: 自动调整大小以适应容器
  - `unicode11`: Unicode 11 支持
  - `web-links`: 链接检测和处理
  - `webgl`: WebGL 渲染加速

### 可视化库

#### @observablehq/plot ^0.6.17
```json
"@observablehq/plot": "^0.6.17"
```
- 声明式 JavaScript 可视化库
- 用于分析页面的图表
- 基于 D3，但更易用

#### @react-three/fiber ^9.6.0 & three.js ^0.180.0
```json
"@react-three/fiber": "^9.6.0",
"three": "^0.180.0"
```
- React 渲染器 for Three.js
- 3D 可视化支持
- WebGL 渲染

#### leva ^0.10.1
```json
"leva": "^0.10.1"
```
- React 的 GUI 控制面板
- 调试和参数调整
- 可扩展的控件

### 动画库

#### GSAP 3.15.0
```json
"gsap": "^3.15.0"
```
- 专业的 JavaScript 动画库
- 高性能
- 时间线控制
- 复杂动画序列

#### motion ^12.38.0
```json
"motion": "^12.38.0"
```
- 现代动画库（可能是 Motion One）
- 轻量级
- 原生动画支持

#### unicode-animations ^1.0.3
```json
"unicode-animations": "^1.0.3"
```
- Unicode 动画（与 ui-tui 共享）

### 其他工具

#### flag-icons ^7.5.0
```json
"flag-icons": "^7.5.0"
```
- 国旗图标
- 用于语言切换器

### 代码质量

#### ESLint
```json
"eslint": "^9.39.4",
"@eslint/js": "^9.39.4",
"globals": "^17.4.0",
"typescript-eslint": "^8.56.1",
"eslint-plugin-react-hooks": "^7.0.1",
"eslint-plugin-react-refresh": "^0.5.2"
```
- 最新的 ESLint 9.x
- TypeScript ESLint
- React 特定规则

### Web 模块架构特点

#### 插件系统
- **动态加载**: 从 `/api/dashboard/plugins` 获取插件清单
- **插件插槽**: 多个注入点
- **路由覆盖**: 插件可以替换内置页面
- **自定义标签页**: 添加新的导航项

```typescript
// 插件插槽:
PluginSlot name="backdrop"
PluginSlot name="header-banner"
PluginSlot name="header-left"
PluginSlot name="header-right"
PluginSlot name="pre-main"
PluginSlot name="post-main"
PluginSlot name="overlay"
```

#### Context 架构
```typescript
PageHeaderProvider      // 页面头部管理
SystemActionsProvider   // 系统操作（重启、更新）
I18nProvider            // 国际化
ThemeProvider           // 主题
PluginsProvider         // 插件系统
```

#### 持久化聊天
- ChatPage 在路由外部渲染
- 终端实例、WebSocket 连接持久存活
- 使用 CSS `display: none` 切换可见性
- 路由仍然控制 URL 和导航高亮

#### 类型化 API 客户端
```typescript
// lib/api.ts
// 所有后端端点的完全类型化包装
api.getConfig()
api.updateConfig()
api.getEnv()
api.setEnv()
api.listSessions()
// ... 等等
```

#### 主题系统
- CSS 自定义属性
- 支持多种布局变体
- 暗色/亮色切换
- 尊重系统偏好

#### 响应式设计
- 移动端完全支持
- 可折叠侧边栏
- 触摸友好的交互

### Web 模块文件依赖树

```
web/
├── src/
│   ├── main.tsx (入口)
│   │   └── App.tsx
│   │
│   ├── App.tsx (主应用)
│   │   ├── 路由配置
│   │   ├── 侧边栏导航
│   │   ├── 主题/语言切换
│   │   ├── 插件系统集成
│   │   └── 持久化聊天
│   │
│   ├── pages/ (页面组件)
│   │   ├── ChatPage.tsx
│   │   ├── SessionsPage.tsx
│   │   ├── ConfigPage.tsx
│   │   ├── EnvPage.tsx
│   │   ├── ModelsPage.tsx
│   │   ├── AnalyticsPage.tsx
│   │   ├── LogsPage.tsx
│   │   ├── CronPage.tsx
│   │   ├── SkillsPage.tsx
│   │   ├── PluginsPage.tsx
│   │   ├── ProfilesPage.tsx
│   │   └── DocsPage.tsx
│   │
│   ├── components/ (组件)
│   │   ├── ui/ (UI 基元)
│   │   │   ├── card.tsx
│   │   │   ├── confirm-dialog.tsx
│   │   │   ├── input.tsx
│   │   │   ├── label.tsx
│   │   │   └── separator.tsx
│   │   ├── AutoField.tsx
│   │   ├── Backdrop.tsx
│   │   ├── BottomPickSheet.tsx
│   │   ├── ChatSidebar.tsx
│   │   ├── DeleteConfirmDialog.tsx
│   │   ├── LanguageSwitcher.tsx
│   │   ├── Markdown.tsx
│   │   ├── ModelInfoCard.tsx
│   │   ├── ModelPickerDialog.tsx
│   │   ├── NouisTypography.tsx
│   │   ├── OAuthLoginModal.tsx
│   │   ├── OAuthProvidersCard.tsx
│   │   ├── PlatformsCard.tsx
│   │   ├── SidebarFooter.tsx
│   │   ├── SidebarStatusStrip.tsx
│   │   ├── SlashPopover.tsx
│   │   ├── ThemeSwitcher.tsx
│   │   ├── Toast.tsx
│   │   └── ToolCall.tsx
│   │
│   ├── contexts/ (Context)
│   │   ├── PageHeaderProvider.tsx
│   │   ├── page-header-context.ts
│   │   ├── SystemActions.tsx
│   │   └── system-actions-context.ts
│   │
│   ├── hooks/ (Hooks)
│   │   ├── usePageHeader.ts
│   │   ├── useSystemActions.ts
│   │   ├── useI18n.ts
│   │   ├── useTheme.ts
│   │   └── usePlugins.ts
│   │
│   ├── lib/ (工具库)
│   │   ├── api.ts (API 客户端)
│   │   ├── utils.ts (cn() 等)
│   │   └── dashboard-flags.ts
│   │
│   ├── plugins/ (插件系统)
│   │   ├── PluginPage.tsx
│   │   ├── PluginSlot.tsx
│   │   └── usePlugins.ts
│   │
│   ├── themes/ (主题系统)
│   ├── i18n/ (国际化)
│   └── index.css (样式入口)
│
├── index.html (HTML 模板)
├── vite.config.ts (Vite 配置)
└── 配置文件
    ├── tsconfig.json
    ├── tsconfig.app.json
    ├── tsconfig.node.json
    ├── eslint.config.js
    └── package.json
```

---

## Website 模块技术栈

### 核心框架

#### Docusaurus 3.9.2
```json
"@docusaurus/core": "3.9.2",
"@docusaurus/preset-classic": "3.9.2"
```
- **现代静态网站生成器**: 基于 React
- **经典预设**: 包含文档、博客、主题
- **MDX 支持**: Markdown + JSX
- **版本化文档**: 内置支持
- **国际化**: 内置 i18n 支持

#### React 19.0.0
```json
"react": "^19.0.0",
"react-dom": "^19.0.0"
```
- 与 web 和 ui-tui 模块保持版本一致
- 用于自定义页面和组件

### 主题与插件

#### @docusaurus/theme-mermaid ^3.9.2
```json
"@docusaurus/theme-mermaid": "^3.9.2"
```
- Mermaid 图表支持
- 代码块渲染为图表
- 亮色/暗色主题适配

#### @easyops-cn/docusaurus-search-local ^0.55.1
```json
"@easyops-cn/docusaurus-search-local": "^0.55.1"
```
- **离线本地搜索**: 无需 Algolia
- **多语言支持**: 英文、中文
- **哈希索引**: 快速搜索
- **可配置高亮**: 项目中禁用了高亮
- **文件排除**: 排除自动生成的技能文档

### 内容处理

#### @mdx-js/react ^3.0.0
```json
"@mdx-js/react": "^3.0.0"
```
- MDX 运行时
- 在 Markdown 中使用 React 组件

#### prism-react-renderer ^2.3.0
```json
"prism-react-renderer": "^2.3.0"
```
- 代码语法高亮
- 自定义主题支持
- 配置了多种语言:
  - bash
  - yaml
  - json
  - python
  - toml

### 样式工具

#### clsx ^2.0.0
```json
"clsx": "^2.0.0"
```
- 条件类名构建（与 web 模块相同）

### 类型安全

#### TypeScript ~5.6.2
```json
"typescript": "~5.6.2"
```
- 类型检查
- 配置: `tsconfig.json`

#### @docusaurus/module-type-aliases & @docusaurus/types
```json
"@docusaurus/module-type-aliases": "3.9.2",
"@docusaurus/types": "3.9.2"
```
- Docusaurus 的 TypeScript 类型
- 路径别名类型支持

### 开发工具

#### @docusaurus/tsconfig
```json
"@docusaurus/tsconfig": "3.9.2"
```
- Docusaurus 的推荐 TypeScript 配置

### Website 模块架构特点

#### 多语言架构
```
i18n/
├── en/ (默认)
├── zh-Hans/ (简体中文)
└── ko/ (韩语)
```
- 三种语言支持
- 导航栏语言切换器
- 翻译后的文档内容

#### 文档组织
- 文档在根路径 `/`（不是 `/docs`）
- 可隐藏的侧边栏
- 自动折叠分类
- 编辑链接指向 GitHub

#### 自定义组件
```typescript
UserStoriesCollage  // 用户故事拼贴
SkillsPage          // 自定义技能页面
```

#### 自定义数据
```json
// src/data/userStories.json
// 用户故事数据
```

#### 预构建脚本
```javascript
// scripts/prebuild.mjs
// 在 start 和 build 前运行
// 可能生成技能文档
```

#### 图表规范
- 禁止 ASCII 框图
- 使用 Mermaid 代替
- CI 自动检查（`lint:diagrams`）

### Website 模块文件依赖树

```
website/
├── docs/ (文档源文件)
│   ├── getting-started/
│   ├── user-guide/
│   │   └── skills/
│   │       ├── bundled/ (自动生成)
│   │       └── optional/ (自动生成)
│   ├── developer-guide/
│   └── reference/
│
├── i18n/ (翻译文件)
│   ├── en/
│   ├── zh-Hans/
│   └── ko/
│
├── src/
│   ├── components/
│   │   └── UserStoriesCollage/
│   │       ├── index.tsx
│   │       └── styles.module.css
│   ├── pages/
│   │   ├── index.tsx (可选)
│   │   └── skills/
│   │       ├── index.tsx
│   │       └── styles.module.css
│   ├── css/
│   │   └── custom.css
│   └── data/
│       └── userStories.json
│
├── static/ (静态资源)
│   └── img/
│
├── scripts/
│   └── prebuild.mjs
│
├── docusaurus.config.ts (配置)
├── sidebars.ts (侧边栏)
└── 配置文件
    ├── tsconfig.json
    └── package.json
```

---

## 技术栈对比与分析

### 构建工具对比

| 特性 | ui-tui | web | website |
|------|--------|-----|---------|
| **构建工具** | 自定义 esbuild 脚本 | Vite 7 | Docusaurus (Webpack) |
| **开发服务器** | tsx watch | Vite Dev Server | Docusaurus Dev Server |
| **HMR** | 部分支持 | 完整支持 | 完整支持 |
| **TypeScript** | 5.7 | 5.9 | 5.6 |
| **打包输出** | Node.js 可执行 | SPA 静态资源 | 静态网站 |

**分析**:
- **ui-tui**: 自定义 esbuild 配置，针对 Node.js 环境优化
- **web**: Vite 提供极快的开发体验，现代前端的首选
- **website**: Docusaurus 封装了 Webpack，针对文档站点优化

### React 生态对比

| 特性 | ui-tui | web | website |
|------|--------|-----|---------|
| **React 版本** | 19.2.4 | 19.2.4 | 19.0.0 |
| **渲染目标** | Ink (终端) | React DOM (浏览器) | React DOM (浏览器) |
| **路由** | 自定义 | React Router 7 | Docusaurus 路由 |
| **状态管理** | Nanostores | Context + Hooks | Docusaurus 状态 |
| **组件库** | 自定义 Ink 组件 | @nous-research/ui | Docusaurus 主题 |

**分析**:
- 所有模块使用 React 19，保持生态一致
- 不同的渲染目标适配不同环境
- ui-tui 使用轻量级的 Nanostores，其他使用 Context

### 样式系统对比

| 特性 | ui-tui | web | website |
|------|--------|-----|---------|
| **样式方法** | Ink 样式 API | Tailwind CSS v4 | CSS Modules + Infima |
| **CSS-in-JS** | 内置 | 无 | 无 |
| **原子 CSS** | 否 | 是 | 否 |
| **主题系统** | 自定义 CSS-in-JS | CSS 自定义属性 | Docusaurus 主题 |
| **暗色模式** | 支持 | 支持 | 支持 |

**分析**:
- web 模块采用现代化的 Tailwind v4
- ui-tui 受限于终端环境，使用 Ink 样式系统
- website 使用 Docusaurus 的主题系统

### 状态管理对比

| 特性 | ui-tui | web | website |
|------|--------|-----|---------|
| **主要方案** | Nanostores | Context + Hooks | Docusaurus 内置 |
| **复杂度** | 中等 | 中等 | 低 |
| **异步状态** | GatewayClient 处理 | React Query/SWR? | 无 |
| **表单状态** | 自定义 | 自定义 | 无 |
| **持久化** | 输入历史 | 无 | 无 |

**分析**:
- ui-tui 需要处理复杂的 IPC 状态，选择了轻量的 Nanostores
- web 使用 React Context 配合自定义 Hooks
- website 状态需求最小，使用 Docusaurus 内置功能

### 类型安全对比

| 特性 | ui-tui | web | website |
|------|--------|-----|---------|
| **TypeScript** | 严格 | 严格 | 是 |
| **API 类型** | 完整类型化 | 完整类型化 | N/A |
| **组件 Props** | 类型化 | 类型化 | 类型化 |
| **配置类型** | 类型化 | 类型化 | 类型化 |

**分析**:
- 所有模块都采用严格的 TypeScript
- API 客户端完全类型化是亮点
- 类型安全是项目的核心价值

### 测试框架对比

| 特性 | ui-tui | web | website |
|------|--------|-----|---------|
| **测试框架** | Vitest | - | - |
| **单元测试** | 支持 | - | - |
| **组件测试** | 支持 | - | - |
| **E2E 测试** | - | - | - |

**分析**:
- ui-tui 模块有完整的测试设置
- web 和 website 模块测试较少（可能在其他地方）
- Vitest 是现代选择

---

## 最佳实践与设计模式

### 1. 自定义 Hooks 模式

所有模块都大量使用自定义 Hooks:

```typescript
// ui-tui 中的模式
function useComposerState() {
  const [state, setState] = useState(...)
  const actions = useMemo(() => ({ ... }), [])
  return [state, actions] as const
}

// web 中的模式
function usePlugins() {
  const [manifests, setManifests] = useState(...)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    api.getPlugins().then(setManifests)
  }, [])
  
  return { manifests, loading }
}
```

### 2. Context + Provider 模式

```typescript
// Context 创建
const GatewayContext = createContext<GatewayClient | null>(null)

// Provider 组件
function GatewayProvider({ children, gw }: PropsWithChildren<{ gw: GatewayClient }>) {
  return (
    <GatewayContext.Provider value={gw}>
      {children}
    </GatewayContext.Provider>
  )
}

// 使用 Hook
function useGateway() {
  const gw = useContext(GatewayContext)
  if (!gw) throw new Error('GatewayProvider missing')
  return gw
}
```

### 3. 插件/插槽系统

web 模块的插件系统是优秀的设计:

```typescript
// 插槽定义
<PluginSlot name="header-left" />
<PluginSlot name="pre-main" />
<PluginSlot name="post-main" />

// 插件路由
<Route path={manifest.tab.path} element={<PluginPage name={manifest.name} />} />

// 路由覆盖
<Route path="/chat" element={<PluginPage name={overridingPlugin.name} />} />
```

### 4. 原子化状态管理 (Nanostores)

```typescript
// 原子定义
import { atom } from 'nanostores'

export const $uiFlags = atom({
  statusBarVisible: true,
  showDetails: false
})

// 使用
import { useStore } from '@nanostores/react'

function Component() {
  const flags = useStore($uiFlags)
  // ...
}
```

### 5. 事件驱动架构 (ui-tui)

```typescript
// GatewayClient 作为事件发射器
class GatewayClient extends EventEmitter {
  start() { /* ... */ }
  request(method, params) { /* ... */ }
  
  private publish(event: GatewayEvent) {
    this.emit('event', event)
  }
}

// 事件处理
function createGatewayEventHandler(gw: GatewayClient) {
  gw.on('event', (event) => {
    switch (event.type) {
      case 'message.delta':
        // 处理消息增量
        break
      // ...
    }
  })
}
```

### 6. 类型化 API 客户端

```typescript
// lib/api.ts
export const api = {
  async getConfig(): Promise<Config> {
    const res = await fetch('/api/config')
    return res.json()
  },
  
  async updateConfig(config: Partial<Config>): Promise<void> {
    await fetch('/api/config', {
      method: 'PUT',
      body: JSON.stringify(config)
    })
  },
  // ...
}
```

### 7. 工具函数组合 (cn)

```typescript
// lib/utils.ts
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// 使用
<div className={cn('base-class', condition && 'conditional-class')} />
```

### 8. 组件变体 (CVA)

```typescript
// 使用 class-variance-authority
import { cva, type VariantProps } from 'class-variance-authority'

const buttonVariants = cva('base-classes', {
  variants: {
    variant: {
      primary: 'primary-classes',
      secondary: 'secondary-classes',
    },
    size: {
      sm: 'sm-classes',
      lg: 'lg-classes',
    },
  },
  defaultVariants: {
    variant: 'primary',
    size: 'sm',
  },
})

interface ButtonProps extends VariantProps<typeof buttonVariants> {
  // ...
}

function Button({ variant, size, ...props }: ButtonProps) {
  return <button className={buttonVariants({ variant, size })} {...props} />
}
```

---

## 依赖关系图

### 共享依赖关系

```
react@^19.x.x
  ├── ui-tui
  ├── web
  └── website

typescript@5.x
  ├── ui-tui (5.7)
  ├── web (5.9)
  └── website (5.6)

eslint@9.x
  ├── ui-tui
  └── web

clsx@2.x
  ├── web (2.1.1)
  └── website (2.0.0)

unicode-animations@^1.0.3
  ├── ui-tui
  └── web
```

### 内部依赖关系

```
@hermes/ink (ui-tui/packages/hermes-ink)
  └── ui-tui

@nous-research/ui
  └── web

Python backend
  ├── ui-tui (通过 stdio/WebSocket)
  └── web (通过 HTTP API)
```

### 开发依赖关系

```
ui-tui:
  ├── vitest
  ├── prettier
  └── @babel/* (React Compiler)

web:
  ├── vite
  ├── tailwindcss
  └── @tailwindcss/vite

website:
  ├── @docusaurus/*
  └── @easyops-cn/docusaurus-search-local
```

---

## 总结

### 技术栈亮点

1. **现代化 React 19**: 所有模块采用最新 React
2. **TypeScript 优先**: 全面的类型安全
3. **Vite 生态**: web 模块使用最新 Vite 7
4. **Tailwind v4**: 前沿的 CSS 框架
5. **轻量级状态管理**: Nanostores 在 ui-tui 中的应用
6. **自定义 React 渲染器**: Ink 在终端中的创新应用
7. **插件架构**: web 模块的灵活插件系统
8. **Docusaurus 3.x**: website 模块的现代化文档解决方案

### 架构优势

1. **统一的 React 心智模型**: 跨环境共享知识
2. **类型安全端到端**: 从前端到后端 API 完全类型化
3. **模块化设计**: 清晰的关注点分离
4. **可扩展性**: 插件系统和插槽架构
5. **性能优化**: React Compiler、Vite、esbuild 等

### 未来改进方向

1. **测试覆盖**: 增加 web 和 website 模块的测试
2. **共享组件库**: 考虑在三个模块间共享更多逻辑
3. **统一工具链**: 更多的共享开发工具
4. **性能监控**: 增强现有的性能监控功能
5. **文档自动化**: 进一步自动化文档生成流程

---

## 相关文档

- [UI-TUI 中文文档](../ui-tui/README.zh-CN.md)
- [Web UI 中文文档](../web/README.zh-CN.md)
- [Website 中文文档](../website/README.zh-CN.md)
- [项目主 README](../README.zh-CN.md)
