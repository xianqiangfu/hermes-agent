# Hermes TUI - 终端用户界面

基于 React 和 Ink 的终端用户界面，为 Hermes 提供交互式命令行体验。TypeScript 负责界面渲染，Python 管理会话、工具、模型调用和大多数命令逻辑。

## 快速开始

```bash
# 从项目根目录启动 TUI
hermes --tui
```

## 工作原理

### 架构概述

TUI 采用前后端分离架构：

- **前端 (TypeScript/React/Ink)**: 负责终端渲染、用户交互、状态管理
- **后端 (Python)**: 处理会话、工具调用、模型请求等核心业务逻辑
- **通信**: 通过 JSON-RPC 协议进行进程间通信

### 启动流程

1. 入口文件 `src/entry.tsx` 首先检查标准输入是否为 TTY
2. 如果不是 TTY，立即退出
3. 否则，启动 `GatewayClient` 并渲染 React 应用
4. `GatewayClient` 会 spawn Python 子进程：`python -m tui_gateway.entry`

### Python 解释器解析顺序

1. `HERMES_PYTHON` 环境变量
2. `PYTHON` 环境变量
3. `$VIRTUAL_ENV/bin/python`
4. `./.venv/bin/python`
5. `./venv/bin/python`
6. `python3`（Windows 上为 `python`）

### 通信协议

使用换行分隔的 JSON-RPC 协议通过标准输入输出进行通信：

```
ui-tui/src                  tui_gateway/
-----------                 -------------
entry.tsx                   entry.py
  -> GatewayClient            -> request loop
  -> App                      -> server.py RPC handlers

stdin/stdout: JSON-RPC 请求、响应、事件
stderr: 捕获到内存日志环中
```

格式错误的标准输出行被视为协议噪声，并作为 `gateway.protocol_error` 事件显示。标准错误行成为 `gateway.stderr` 事件。两者都不会直接写入终端。

## 应用模型

`src/app.tsx` 是 UI 的核心组件。重量级逻辑被拆分到 `src/app/` 目录下：

| 文件 | 功能描述 |
|------|----------|
| `createGatewayEventHandler.ts` | 将网关事件映射到状态更新 |
| `createSlashHandler.ts` | 本地斜杠命令分发 |
| `useComposerState.ts` | 草稿、多行缓冲区、队列编辑 |
| `useInputHandlers.ts` | 按键路由 |
| `useTurnState.ts` | Agent 轮次生命周期 |
| `overlayStore.ts` | 覆盖层状态的 nanostore |
| `uiStore.ts` | UI 标志的 nanostore |
| `gatewayContext.tsx` | 网关客户端的 React 上下文 |
| `constants.ts`, `helpers.ts`, `interfaces.ts` | 常量、辅助函数、接口定义 |

### 顶层状态管理

- 对话记录和流式传输状态
- 排队消息和输入历史
- 会话生命周期
- 工具进度和推理文本
- 批准、澄清、sudo 和密码输入的提示流程
- 斜杠命令路由
- 自动完成和路径补全
- 来自网关皮肤数据的主题状态

### Markdown 渲染

助手输出有两种渲染方式：
- 如果负载已包含 ANSI，`messageLine.tsx` 直接打印
- 否则，`components/markdown.tsx` 将 Markdown 子集渲染为 Ink 组件

支持的 Markdown 功能：标题、列表、引用、表格、代码块、差异着色、内联代码、强调、链接、纯文本 URL。

## 快捷键和交互

### 主聊天输入

| 按键 | 行为 |
|------|------|
| `Enter` | 提交当前草稿 |
| 空 `Enter` 两次 | 如果存在排队消息且代理忙，中断当前运行；如果存在排队消息且代理空闲，发送下一条排队消息 |
| `Shift+Enter` / `Alt+Enter` | 在当前草稿中插入新行 |
| `\` + `Enter` | 将行追加到多行缓冲区（作为不支持修饰键的终端的后备方案） |
| `Ctrl+C` | 中断活动运行，或清除当前草稿，或如果没有待处理内容则退出 |
| `Ctrl+D` | 退出 |
| `Cmd/Ctrl+G` / `Alt+G` | 打开 `$EDITOR` 编辑当前草稿（在 VSCode/Cursor 中使用 `Alt+G` - 它们将主键绑定到查找下一个） |
| `Ctrl+L` | 新会话（等同于 `/clear`） |
| `Ctrl+V` / `Alt+V` | 先粘贴文本，然后在适用时回退到图像/路径附件 |
| `Tab` | 应用活动的自动完成 |
| `Up/Down` | 如果自动完成列表打开则循环选项；否则先编辑排队消息，然后遍历输入历史 |
| `Left/Right` | 移动光标 |
| 带修饰键的 `Left/Right` | 当终端发送带有箭头键的 `Ctrl` 或 `Meta` 时按单词移动 |
| `Home` / `Ctrl+A` | 行首 |
| `End` / `Ctrl+E` | 行尾 |
| `Backspace` | 删除光标左侧的字符 |
| `Delete` | 删除光标右侧的字符 |
| 带修饰键的 `Backspace` | 删除前一个单词 |
| 带修饰键的 `Delete` | 删除后一个单词 |
| `Ctrl+W` | 删除前一个单词 |
| `Ctrl+U` | 从光标删除到行首 |
| `Ctrl+K` | 从光标删除到行尾 |
| `Meta+B` / `Meta+F` | 按单词移动 |
| `!cmd` | 通过网关执行 shell 命令 |
| `{!cmd}` | 发送前的内联 shell 插值；排队的草稿在发送前保留原始文本 |

### 提示和选择器模式

| 上下文 | 按键 | 行为 |
|--------|------|------|
| 批准提示 | `Up/Down`, `Enter` | 移动并确认选中的批准选项 |
| 批准提示 | `o`, `s`, `a`, `d` | 快速选择 "once"、"session"、"always"、"deny" |
| 批准提示 | `Esc`, `Ctrl+C` | 拒绝 |
| 带选项的澄清提示 | `Up/Down`, `Enter` | 移动并确认选中的选项 |
| 带选项的澄清提示 | 单个数字 | 快速选择匹配编号的选项 |
| 带选项的澄清提示 | 在 "Other" 上按 `Enter` | 切换到自由文本输入 |
| 澄清自由文本模式 | `Enter` | 提交键入的答案 |
| sudo / 密码提示 | `Enter` | 提交键入的值 |
| sudo / 密码提示 | `Ctrl+C` | 通过发送空响应取消 |
| 恢复会话选择器 | `Up/Down`, `Enter` | 移动并恢复选中的会话 |
| 恢复会话选择器 | `1-9` | 快速选择前九个可见会话之一 |
| 恢复会话选择器 | `Esc`, `Ctrl+C` | 关闭选择器 |

### 交互规则

- 当代理忙时输入的纯文本会排队而不是立即发送
- 斜杠命令和 `!cmd` 不排队；它们即使在运行活动时也立即执行
- 队列在每个助手响应后自动排空，除非当前正在编辑排队的项目
- 当你不在多行模式时，`Up/Down` 优先考虑排队消息编辑而不是历史记录
- 排队的草稿在你编辑时保留其原始 `!cmd` 和 `{!cmd}` 文本。shell 命令和插值在排队的项目实际发送时执行
- 如果你将排队的项目加载到输入中并重新提交纯文本，该排队项目将被替换，从队列预览中删除，并提升为下一个发送。如果代理仍在忙，编辑后的项目将移到队列前面并在当前运行完成后发送
- 自动完成请求有 60ms 的去抖动。以 `/` 开头的输入使用 `complete.slash`。以 `./`、`../`、`~/`、`/` 或 `@` 开头的尾随标记使用 `complete.path`
- 文本粘贴直接插入到草稿中。不会进行换行展平
- `Cmd/Ctrl+G`（或 VSCode/Cursor 中的 `Alt+G`，它们拦截主键用于查找下一个）将当前草稿（包括任何多行缓冲区）写入临时文件，暂停 Ink，启动 `$EDITOR`，然后如果编辑器正常退出则恢复 TUI 并提交保存的文本
- 输入历史存储在 `~/.hermes/.hermes_history` 或 `HERMES_HOME` 下

## 提示流程

Python 网关可以暂停主循环并请求结构化输入：

| 提示类型 | 描述 |
|----------|------|
| `approval.request` | 允许一次、会话中允许、始终允许或拒绝 |
| `clarify.request` | 从选项中选择或输入自定义答案 |
| `sudo.request` | 掩码密码输入 |
| `secret.request` | 命名环境变量的掩码值输入 |
| `session.list` | 供 `/resume` 使用的会话选择器 |

这些是 `app.tsx` 中的有状态 UI 分支，而不是独立屏幕。

## 命令

本地斜杠处理程序涵盖需要直接客户端行为的内置命令：

| 命令 | 描述 |
|------|------|
| `/help` | 显示帮助 |
| `/quit`, `/exit`, `/q` | 退出 TUI |
| `/clear` | 清除会话 |
| `/new` | 新建会话 |
| `/compact` | 压缩对话记录 |
| `/resume` | 恢复会话 |
| `/copy` | 复制选中的助手响应（通过 OSC 52） |
| `/paste` | 粘贴剪贴板图像 |
| `/details` | 控制思维/工具详细信息可见性 |
| `/logs` | 显示日志 |
| `/statusbar`, `/sb` | 切换状态栏 |
| `/queue` | 显示队列 |
| `/undo` | 撤销 |
| `/retry` | 重试 |

其他所有命令都会传递给：
1. `slash.exec`
2. `command.dispatch`

这样 Python 可以管理别名、插件、技能和注册表支持的命令，而无需在 TUI 中复制逻辑。

## 事件类型

客户端目前处理的主要事件类型：

| 事件 | 负载 |
|------|------|
| `gateway.ready` | `{ skin? }` |
| `session.info` | 横幅 + 工具/技能面板的会话元数据 |
| `message.start` | 开始助手流式传输 |
| `message.delta` | `{ text, rendered? }` |
| `message.complete` | `{ text, rendered?, usage, status }` |
| `thinking.delta` | `{ text }` |
| `reasoning.delta` | `{ text }` |
| `reasoning.available` | `{ text }` |
| `status.update` | `{ kind, text }` |
| `tool.start` | `{ tool_id, name, context? }` |
| `tool.progress` | `{ name, preview }` |
| `tool.complete` | `{ tool_id, name }` |
| `clarify.request` | `{ question, choices?, request_id }` |
| `approval.request` | `{ command, description }` |
| `sudo.request` | `{ request_id }` |
| `secret.request` | `{ prompt, env_var, request_id }` |
| `background.complete` | `{ task_id, text }` |
| `error` | `{ message }` |
| `gateway.stderr` | 从子进程 stderr 合成 |
| `gateway.protocol_error` | 从格式错误的 stdout 合成 |

## 主题模型

客户端从 `theme.ts` 中的 `DEFAULT_THEME` 开始，然后合并来自 `gateway.ready` 的网关皮肤数据。

### 品牌覆盖

- 代理名称
- 提示符号
- 欢迎文本
- 告别文本

### 颜色覆盖

- 横幅标题、强调色、边框、正文、暗淡色
- 标签、成功、错误、警告

`branding.tsx` 使用这些值来显示徽标、会话面板和更新通知。

## 文件结构

```text
ui-tui/
  packages/hermes-ink/  # 分叉的 Ink 渲染器（本地依赖）
  src/
    entry.tsx           # TTY 检查 + render()
    app.tsx             # 顶层 Ink 树，组合 src/app/*
    gatewayClient.ts    # 子进程 + JSON-RPC 桥接
    theme.ts            # 默认调色板 + 皮肤合并
    constants.ts        # 显示常量、快捷键、工具标签
    types.ts            # 共享客户端类型
    banner.ts           # ASCII 艺术数据

    app/
      createGatewayEventHandler.ts  # 事件 → 状态映射
      createSlashHandler.ts         # 本地斜杠分发
      useComposerState.ts           # 草稿 + 多行 + 队列编辑
      useInputHandlers.ts           # 按键路由
      useTurnState.ts               # Agent 轮次生命周期
      overlayStore.ts               # 覆盖层的 nanostores
      uiStore.ts                    # UI 标志的 nanostores
      gatewayContext.tsx            # 网关客户端的 React 上下文
      constants.ts                  # 应用级常量
      helpers.ts                    # 纯辅助函数
      interfaces.ts                 # 内部接口
      slash/                        # 斜杠命令实现
        commands/
          core.ts                   # 核心命令
          debug.ts                  # 调试命令
          ops.ts                    # 操作命令
          session.ts                # 会话命令
          setup.ts                  # 设置命令
        registry.ts                 # 命令注册表
        types.ts                    # 命令类型

    components/
      appChrome.tsx      # 状态栏、输入行、自动完成
      appLayout.tsx      # 顶层布局组合
      appOverlays.tsx    # 覆盖层路由（选择器、提示）
      branding.tsx       # 横幅 + 会话摘要
      markdown.tsx       # Markdown 到 Ink 的渲染
      maskedPrompt.tsx   # sudo / 密码的掩码输入
      messageLine.tsx    # 对话记录行
      modelPicker.tsx    # 模型切换选择器
      prompts.tsx        # 批准 + 澄清流程
      queuedMessages.tsx # 排队输入预览
      sessionPicker.tsx  # 会话恢复选择器
      textInput.tsx      # 自定义行编辑器
      thinking.tsx       # 加载动画、推理、工具活动
      agentsOverlay.tsx  # 代理选择覆盖层

    hooks/
      useCompletion.ts   # 自动完成（斜杠 + 路径）
      useInputHistory.ts # 持久历史导航
      useQueue.ts        # 排队消息管理
      useVirtualHistory.ts # 选择器的内存历史

    lib/
      history.ts         # 持久输入历史
      messages.ts        # 消息格式化辅助函数
      osc52.ts           # OSC 52 剪贴板复制
      rpc.ts             # JSON-RPC 类型辅助函数
      text.ts            # 文本辅助函数、ANSI 检测、预览
      gracefulExit.ts    # 优雅退出处理
      memory.ts          # 内存管理
      memoryMonitor.ts   # 内存监控
      terminalModes.ts   # 终端模式重置
      perfPane.ts        # 性能面板
      fpsStore.ts        # FPS 存储

    types/
      hermes-ink.d.ts    # @hermes/ink 的类型声明

    __tests__/           # vitest 测试套件
```

### 相关 Python 端

```text
tui_gateway/
  entry.py             # stdio 入口点
  server.py            # RPC 处理程序和会话逻辑
  render.py            # 可选的 rich/ANSI 桥接
  slash_worker.py      # 斜杠命令的持久 HermesCLI 子进程
```

## 本地开发命令

```bash
# 进入 ui-tui 目录
cd ui-tui

# 安装依赖
npm install

# 开发模式（带热重载）
npm run dev

# 启动（无热重载）
npm start

# 构建
npm run build

# 类型检查
npm run type-check

# 代码检查
npm run lint

# 代码检查并自动修复
npm run lint:fix

# 格式化
npm run fmt

# 修复（lint:fix + fmt）
npm run fix

# 测试
npm test

# 测试监听模式
npm run test:watch
```

## 配置

### 环境变量

| 变量 | 描述 |
|------|------|
| `HERMES_PYTHON` | Python 解释器路径 |
| `HERMES_HOME` | Hermes 主目录（存储历史等） |
| `HERMES_TUI_GATEWAY_URL` | 附加模式的网关 URL（不 spawn Python） |
| `HERMES_TUI_SIDECAR_URL` | 附加模式的 sidecar URL |
| `HERMES_TUI_STARTUP_TIMEOUT_MS` | 启动超时（默认 15000ms） |
| `HERMES_TUI_RPC_TIMEOUT_MS` | RPC 请求超时（默认 120000ms） |
| `HERMES_HEAPDUMP_ON_START` | 启动时执行堆转储（设置为 "1" 启用） |

### 架构模式

#### GatewayClient

`GatewayClient` 是 TypeScript 和 Python 之间的桥接器，支持两种模式：

1. **Spawn 模式**: 启动本地 Python 子进程（默认）
2. **Attach 模式**: 通过 WebSocket 连接到已运行的网关（`HERMES_TUI_GATEWAY_URL`）

主要功能：
- JSON-RPC 请求/响应处理
- 事件缓冲和分发
- 超时管理
- 日志环形缓冲
- 自动重连支持

#### 状态管理

使用 **nanostores** 进行轻量级状态管理：
- `uiStore`: UI 标志（状态栏可见性等）
- `overlayStore`: 覆盖层状态（提示、选择器）
- `spawnHistoryStore`: 生成历史
- `delegationStore`: 委托状态

#### 自定义组件

TUI 包含多个自定义 Ink 组件，位于 `packages/hermes-ink/`，为终端渲染提供增强功能。

## 注意事项

1. **终端兼容性**: TUI 需要支持 ANSI 转义序列的现代终端
2. **TTY 要求**: 如果标准输入不是 TTY，TUI 将立即退出
3. **内存监控**: 包含自动内存监控，在内存使用率高时会生成堆转储
4. **事件缓冲**: 在应用准备好之前，网关事件会被缓冲
5. **插件支持**: 支持插件扩展功能

## 性能优化

- React Compiler 用于优化渲染
- 高效的事件处理
- 内存监控和自动清理
- FPS 追踪选项
- 性能面板用于调试

## 相关文档

- [Web UI 文档](../web/README.zh-CN.md)
- [项目主 README](../README.zh-CN.md)
