# Hermes Agent 最佳实践与踩坑指南

本指南收集了使用 Hermes Agent 的最佳实践、常见问题和性能优化建议。

## 目录

- [开发环境最佳实践](#开发环境最佳实践)
- [生产环境最佳实践](#生产环境最佳实践)
- [安全最佳实践](#安全最佳实践)
- [常见踩坑指南](#常见踩坑指南)
- [性能优化建议](#性能优化建议)
- [成本优化建议](#成本优化建议)
- [技能开发最佳实践](#技能开发最佳实践)
- [故障排查步骤](#故障排查步骤)

## 开发环境最佳实践

### 使用独立的配置目录

为开发和生产环境使用不同的配置目录，避免混淆。

```bash
# 开发环境
export HERMES_HOME=~/.hermes-dev

# 测试环境
export HERMES_HOME=~/.hermes-test

# 生产环境
export HERMES_HOME=~/.hermes
```

### 配置开发环境

```yaml
# ~/.hermes-dev/config.yaml
agent:
  verbose: true
  reasoning_effort: "high"

display:
  tool_progress: "verbose"
  show_reasoning: true

# 使用更经济的模型进行开发
model:
  default: "google/gemini-3-flash-preview"
```

### 设置 Git 工作流

```bash
# 配置 Git 用户信息
git config user.name "Your Name"
git config user.email "your.email@example.com"

# 为项目设置特定的 user.name/email（可选）
cd hermes-agent
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### 使用虚拟环境

始终使用项目的虚拟环境：

```bash
# 激活虚拟环境
source venv/bin/activate

# 或使用提供的脚本
./hermes  # 自动检测并使用虚拟环境
```

## 生产环境最佳实践

### 使用 Docker 部署

使用 Docker 进行部署，提供隔离和可重现性。

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  hermes:
    image: ghcr.io/nousresearch/hermes-agent:latest
    container_name: hermes-gateway
    restart: unless-stopped
    network_mode: host
    user: "1000:1000"  # 使用非 root 用户
    read_only: true  # 只读文件系统
    tmpfs:
      - /tmp:rw,size=100m
    volumes:
      - /home/hermes/.hermes:/opt/data:rw
    environment:
      - HERMES_UID=1000
      - HERMES_GID=1000
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 设置监控和日志

```yaml
# 配置日志轮转
display:
  # ...

# 设置健康检查
agent:
  gateway_timeout: 1800
```

### 定期备份

```bash
#!/bin/bash
# backup-hermes.sh

BACKUP_DIR=/var/backups/hermes
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

mkdir -p $BACKUP_DIR

# 备份配置和数据
tar -czf $BACKUP_DIR/hermes_$DATE.tar.gz \
    ~/.hermes \
    --exclude='~/.hermes/logs' \
    --exclude='~/.hermes/.venv'

# 删除旧备份
find $BACKUP_DIR -name "hermes_*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "备份完成: hermes_$DATE.tar.gz"
```

添加到 crontab：

```bash
crontab -e
# 添加：0 2 * * * /path/to/backup-hermes.sh
```

### 资源限制

```yaml
# ~/.hermes/config.yaml
terminal:
  backend: "docker"
  container_cpu: 1.0
  container_memory: 2048  # MB
  container_disk: 10240   # MB

agent:
  max_turns: 60
  gateway_timeout: 1800
```

## 安全最佳实践

### 密钥管理

```bash
# .env 文件权限应该是 600
chmod 600 ~/.hermes/.env

# 不要将 .env 提交到 Git
echo ".env" >> .gitignore
```

### 终端后端安全

优先使用隔离的后端：

```yaml
terminal:
  backend: "docker"  # 比 local 安全
  docker_image: "nikolaik/python-nodejs:python3.11-nodejs20"
  docker_mount_cwd_to_workspace: false  # 不要挂载宿主机目录
  docker_run_as_host_user: true  # 使用非 root 用户
```

### 用户访问控制

```yaml
# 消息平台允许列表
platforms:
  telegram:
    guest_mode: false

# Discord 配置
discord:
  require_mention: true
  auto_thread: true
```

### 审计日志

```bash
# 启用详细日志
HERMES_LOG_LEVEL=INFO hermes gateway start

# 监控关键操作
grep "terminal\|write_file\|delete_file" ~/.hermes/logs/*.log
```

### 命令审批（如果可用）

```python
# 自定义命令审批钩子
def approve_command(command):
    """审批危险命令"""
    dangerous_commands = ["rm -rf", "mkfs", ":(){ :|: & };:", "dd if="]
    for cmd in dangerous_commands:
        if cmd in command:
            return False
    return True
```

## 常见踩坑指南

### 1. 配置文件权限问题

**问题**：`PermissionError` 或配置不生效

**解决方案**：

```bash
# 修复权限
chown -R $USER:$USER ~/.hermes
chmod 700 ~/.hermes
chmod 600 ~/.hermes/config.yaml
chmod 600 ~/.hermes/.env
```

### 2. Docker 后端无法启动

**问题**：`Cannot connect to Docker daemon`

**解决方案**：

```bash
# 检查 Docker 是否运行
docker ps

# 将用户添加到 docker 组
sudo usermod -aG docker $USER
# 重新登录或使用 newgrp
newgrp docker
```

### 3. API 密钥不生效

**问题**：提示 API 密钥未设置，但已在 .env 中配置

**解决方案**：

```bash
# 检查 .env 文件格式
cat -A ~/.hermes/.env
# 注意是否有多余的空格、换行等

# 验证环境变量是否被读取
hermes config list
```

### 4. 内存溢出

**问题**：长时间运行后内存占用高

**解决方案**：

```yaml
# 启用上下文压缩
compression:
  enabled: true
  threshold: 0.50  # 较早开始压缩

# 设置会话重置策略
session_reset:
  mode: "both"
  idle_minutes: 1440  # 24小时
  at_hour: 4  # 凌晨4点
```

### 5. 终端命令超时

**问题**：命令执行时间过长导致超时

**解决方案**：

```yaml
terminal:
  timeout: 300  # 增加超时时间（秒）
  lifetime_seconds: 600
```

### 6. 平台消息不响应

**问题**：消息平台（如 Telegram）收到消息但无响应

**解决方案**：

```bash
# 查看网关日志
sudo journalctl -u hermes-gateway -f

# 检查用户是否在允许列表中
# 查看用户 ID，确保已添加到允许列表
```

### 7. 上下文过长错误

**问题**：`Context window exceeded` 错误

**解决方案**：

```yaml
# 确保压缩已启用
compression:
  enabled: true
  threshold: 0.50
  protect_last_n: 20
  protect_first_n: 3

# 使用支持更大上下文的模型
model:
  default: "anthropic/claude-sonnet-4.6"  # 128K 上下文
```

### 8. 依赖安装问题

**问题**：依赖安装失败或版本冲突

**解决方案**：

```bash
# 使用 uv 重新安装
uv sync --frozen

# 清除已安装的包，重新安装
rm -rf venv
uv venv venv --python 3.11
source venv/bin/activate
uv pip install -e ".[all,dev]"
```

### 9. 技能未加载

**问题**：技能未被代理识别或使用

**解决方案**：

```yaml
# 确保技能目录配置正确
skills:
  external_dirs:
    - "~/.hermes/skills"
```

检查技能文件格式是否符合要求：
- 使用 .md 扩展名
- 文件格式正确（标题、章节）

### 10. 中文乱码或编码问题

**问题**：输出中出现乱码

**解决方案**：

```bash
# 设置正确的 locale
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# 或在启动命令中设置
LANG=en_US.UTF-8 hermes
```

## 性能优化建议

### 模型选择

| 任务类型 | 推荐模型 | 理由 |
|---------|---------|------|
| 日常对话、简单任务 | `google/gemini-3-flash-preview` | 快速、经济 |
| 中等复杂度任务 | `anthropic/claude-sonnet-4.6` | 平衡性能和成本 |
| 复杂推理、长文档 | `anthropic/claude-opus-4.6` | 最强性能 |
| 代码任务 | `kimi/kimi-k2.5` 或 `openai/gpt-4o` | 代码优化 |

### 上下文管理

```yaml
# 尽早压缩以节省 token
compression:
  enabled: true
  threshold: 0.50  # 50% 时开始压缩
  target_ratio: 0.20
  protect_last_n: 20
  protect_first_n: 3

# 定期重置会话
session_reset:
  mode: "both"
  idle_minutes: 1440
```

### 工具调用优化

```yaml
# 限制工具循环次数
agent:
  max_turns: 60

# 启用工具循环保护
tool_loop_guardrails:
  warnings_enabled: true
  hard_stop_enabled: true
```

### 批处理操作

对于批量任务：

```python
# 使用批量轨迹生成
# batch_runner.py 可以高效处理批量任务
```

### 缓存策略

```yaml
model:
  openrouter:
    response_cache: true
    response_cache_ttl: 300  # 5分钟缓存
```

## 成本优化建议

### 使用经济型模型

```yaml
# 日常使用快速经济型模型
model:
  default: "google/gemini-3-flash-preview"
  # 或 "openai/gpt-4o-mini"

# 仅在需要时使用高级模型
# 让代理在需要时选择切换，或手动切换
```

### 启用缓存

```yaml
model:
  openrouter:
    response_cache: true  # 免费缓存
```

### 上下文压缩

```yaml
compression:
  enabled: true
  threshold: 0.50  # 较早压缩，减少 token 使用
```

### 使用子代理

对于可并行的任务，使用子代理拆分工作：

```python
# 让代理使用 delegate_task 工具
# 子代理使用更经济的模型
```

### 限制工具调用

```yaml
agent:
  max_turns: 40  # 减少不必要的工具调用
```

### 批处理

```python
# 批量处理任务，而非单次处理
# 使用 batch_runner.py
```

## 技能开发最佳实践

### 技能结构

```markdown
# 技能名称

## 描述
简要描述技能用途，要具体。

## 使用场景
- 场景 1：具体场景描述
- 场景 2：具体场景描述
- 何时使用此技能

## 步骤
1. 第一步，具体做什么
2. 第二步，具体做什么
3. 第三步，具体做什么

## 示例
```
示例代码或对话
```

## 注意事项
- 陷阱或常见错误
- 替代方案
- 最佳实践
```

### 技能命名

- 使用小写字母和连字符：`web-scraping`，而非 `WebScraping`
- 名称要具体：`data-analysis-pandas`，而非 `data`
- 包括领域：`devops-docker`，而非 `docker`

### 技能版本控制

考虑为技能添加版本信息：

```markdown
# 技能名称
版本: 1.0
最后更新: 2024-01-15
```

### 技能测试

```python
# 测试技能是否有效加载
from skills import load_skill

skill = load_skill("path/to/skill.md")
assert skill.name is not None
assert skill.description is not None
assert skill.content is not None
```

## 代理人格调教最佳实践

### 简洁明了的系统提示

```yaml
agent:
  personalities:
    my-assistant: |
      你是一个专业的助手。
      特点：简洁、准确、友好。
      避免：过度冗长、不必要的细节。
```

### 特定领域人格

```yaml
agent:
  personalities:
    code-reviewer: |
      你是一个资深代码审查员。
      审查代码时：
      1. 检查潜在的 bug
      2. 代码风格问题
      3. 性能考虑
      4. 安全问题
      提供具体的修改建议。
```

## 故障排查步骤

### 诊断命令

```bash
# 运行内置诊断
hermes doctor

# 查看配置
hermes config list

# 检查版本
hermes --version
```

### 日志查看

```bash
# 查看最新日志
ls -lt ~/.hermes/logs/
tail -f ~/.hermes/logs/session-*.log

# 如果使用 systemd
sudo journalctl -u hermes-gateway -n 100 -f
```

### 常见检查清单

- [ ] 检查 Python 版本：`python --version`（需要 3.11+）
- [ ] 检查虚拟环境是否激活
- [ ] 检查文件权限
- [ ] 检查磁盘空间：`df -h`
- [ ] 检查内存使用：`free -h`
- [ ] 检查网络连接
- [ ] 检查 API 密钥是否正确
- [ ] 检查配置文件 YAML 格式是否正确
- [ ] 检查环境变量是否正确设置

### 增加日志级别

```yaml
# ~/.hermes/config.yaml
agent:
  verbose: true

display:
  tool_progress: "verbose"
```

或使用环境变量：

```bash
HERMES_LOG_LEVEL=DEBUG hermes
```

### 最小配置测试

如果有问题，尝试使用最小配置：

```yaml
# ~/.hermes/config.yaml
model:
  default: "anthropic/claude-opus-4.6"

terminal:
  backend: "local"
```

### 重新初始化配置

如果配置严重出错：

```bash
# 备份配置
mv ~/.hermes ~/.hermes.backup

# 重新创建
mkdir -p ~/.hermes
cp cli-config.yaml.example ~/.hermes/config.yaml
cp .env.example ~/.hermes/.env
# 重新配置
```

## 获取帮助

如果以上步骤无法解决问题：

1. 查看 [GitHub Issues](https://github.com/NousResearch/hermes-agent/issues) 搜索类似问题
2. 加入 [Discord 社区](https://discord.gg/NousResearch) 提问
3. 创建新 Issue，包含：
   - 问题描述
   - 复现步骤
   - 预期行为
   - 实际行为
   - 日志（脱敏后）
   - 环境信息（OS、Python 版本、Hermes 版本）

## 示例配置方案

### 个人使用配置

```yaml
model:
  default: "anthropic/claude-opus-4.6"
  provider: "openrouter"

terminal:
  backend: "local"
  cwd: "."

agent:
  max_turns: 100
  reasoning_effort: "high"

compression:
  enabled: true
  threshold: 0.70

skills:
  creation_nudge_interval: 15

display:
  show_reasoning: false
  streaming: true

platform_toolsets:
  cli: ["hermes-cli"]
```

### 生产服务配置

```yaml
model:
  default: "anthropic/claude-sonnet-4.6"
  provider: "openrouter"

terminal:
  backend: "docker"
  docker_image: "nikolaik/python-nodejs:python3.11-nodejs20"
  docker_mount_cwd_to_workspace: false
  docker_run_as_host_user: true
  timeout: 300
  container_cpu: 2.0
  container_memory: 4096

compression:
  enabled: true
  threshold: 0.50

session_reset:
  mode: "both"
  idle_minutes: 1440
  at_hour: 4

memory:
  memory_enabled: true
  user_profile_enabled: true

stt:
  enabled: true
  provider: "local"

display:
  cleanup_progress: true
  streaming: true

platform_toolsets:
  telegram: ["hermes-telegram"]
  discord: ["hermes-discord"]
```

希望这些最佳实践和踩坑指南对你有所帮助！
