# Hermes Agent 部署文档

本指南介绍如何在不同环境中部署 Hermes Agent，包括本地开发环境、云端服务器、Docker 容器和 Modal 无服务器平台。

## 目录

- [本地部署](#本地部署)
- [云端服务器部署](#云端服务器部署)
- [Docker 部署](#docker-部署)
- [Docker Compose 部署](#docker-compose-部署)
- [Modal 部署](#modal-部署)
- [Daytona 部署](#daytona-部署)
- [反向代理配置](#反向代理配置)
- [生产环境最佳实践](#生产环境最佳实践)

## 本地部署

本地部署适合开发和测试环境。

### 前置要求

- Python 3.11+
- Node.js 18+
- Git

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
```

2. **运行安装脚本**

```bash
./setup-hermes.sh
```

或者手动安装：

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境
uv venv venv --python 3.11
source venv/bin/activate

# 安装依赖
uv pip install -e ".[all,dev]"
```

3. **配置环境**

```bash
# 复制环境变量示例
cp .env.example ~/.hermes/.env

# 编辑配置文件
nano ~/.hermes/.env
```

4. **运行测试**

```bash
# 运行测试套件
python -m pytest tests/ -v
```

5. **启动应用**

```bash
# 方式一：使用虚拟环境中的 hermes
./hermes

# 方式二：如果已创建符号链接
hermes
```

### 开发模式

对于开发工作流，可以使用以下命令：

```bash
# 启动 CLI（自动重载）
hermes

# 运行特定测试
python -m pytest tests/test_specific.py -xvs

# 代码格式化
ruff format .

# 代码检查
ruff check .
```

## 云端服务器部署

在云端服务器（如 AWS EC2、Google Cloud、DigitalOcean、Vultr 等）上部署 Hermes Agent。

### 前置要求

- 一台运行 Linux 的云服务器（推荐 Ubuntu 22.04+）
- 至少 2GB RAM 和 10GB 存储空间
- 域名（可选，用于反向代理）

### 步骤 1：设置服务器

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础依赖
sudo apt install -y build-essential curl git python3 python3-pip \
    python3-venv nodejs npm nginx

# 创建专用用户
sudo useradd -m -s /bin/bash hermes
sudo su - hermes
```

### 步骤 2：安装 Hermes

```bash
# 克隆仓库
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent

# 运行安装脚本
./setup-hermes.sh

# 添加到 PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 步骤 3：配置

```bash
# 创建配置目录
mkdir -p ~/.hermes

# 复制配置文件
cp .env.example ~/.hermes/.env
cp cli-config.yaml.example ~/.hermes/config.yaml

# 编辑配置
nano ~/.hermes/.env
nano ~/.hermes/config.yaml
```

### 步骤 4：设置 systemd 服务

创建服务文件 `/etc/systemd/system/hermes-gateway.service`：

```bash
sudo nano /etc/systemd/system/hermes-gateway.service
```

添加以下内容：

```ini
[Unit]
Description=Hermes Agent Gateway
After=network.target

[Service]
Type=simple
User=hermes
WorkingDirectory=/home/hermes/hermes-agent
Environment="PATH=/home/hermes/.local/bin:/home/hermes/hermes-agent/venv/bin"
ExecStart=/home/hermes/.local/bin/hermes gateway start
Restart=always
RestartSec=10

# 资源限制
Nice=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

启用并启动服务：

```bash
# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务（开机自启）
sudo systemctl enable hermes-gateway

# 启动服务
sudo systemctl start hermes-gateway

# 查看状态
sudo systemctl status hermes-gateway

# 查看日志
sudo journalctl -u hermes-gateway -f
```

### 步骤 5：配置防火墙

```bash
# 允许 SSH
sudo ufw allow 22/tcp

# 如果你使用 Telegram webhook（可选）
sudo ufw allow 443/tcp

# 如果你使用自定义端口
# sudo ufw allow 8443/tcp

# 启用防火墙
sudo ufw enable
```

## Docker 部署

使用 Docker 部署 Hermes Agent，提供隔离的运行环境。

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+（可选）

### 方法一：使用预构建的 Docker 镜像

```bash
# 拉取最新镜像
docker pull ghcr.io/nousresearch/hermes-agent:latest

# 运行容器
docker run -d \
  --name hermes \
  -v ~/.hermes:/opt/data \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  ghcr.io/nousresearch/hermes-agent:latest \
  gateway start
```

### 方法二：从源码构建 Docker 镜像

1. **构建镜像**

```bash
# 克隆仓库
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent

# 构建 Docker 镜像
docker build -t hermes-agent:latest .
```

2. **准备配置**

```bash
# 创建配置目录
mkdir -p ~/.hermes

# 复制环境变量文件
cp .env.example ~/.hermes/.env

# 编辑配置
nano ~/.hermes/.env
```

3. **运行容器**

```bash
# 运行 CLI 模式
docker run -it --rm \
  -v ~/.hermes:/opt/data \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  hermes-agent:latest

# 运行网关模式
docker run -d \
  --name hermes-gateway \
  --network host \
  -v ~/.hermes:/opt/data \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  hermes-agent:latest \
  gateway start

# 运行仪表盘
docker run -d \
  --name hermes-dashboard \
  --network host \
  -v ~/.hermes:/opt/data \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  --depends-on hermes-gateway \
  hermes-agent:latest \
  dashboard --host 127.0.0.1 --no-open
```

### 自定义 Docker 运行参数

```bash
docker run -d \
  --name hermes \
  --network host \
  --restart unless-stopped \
  -v ~/.hermes:/opt/data \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  -e OPENROUTER_API_KEY=your_api_key_here \
  -e TELEGRAM_BOT_TOKEN=your_telegram_token \
  hermes-agent:latest \
  gateway start
```

## Docker Compose 部署

使用 Docker Compose 可以更方便地管理多容器部署。

### 1. 创建 docker-compose.yml

```yaml
version: '3.8'

services:
  gateway:
    build: .
    image: hermes-agent
    container_name: hermes-gateway
    restart: unless-stopped
    network_mode: host
    volumes:
      - ~/.hermes:/opt/data
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - HERMES_UID=${HERMES_UID:-10000}
      - HERMES_GID=${HERMES_GID:-10000}
      # 可选：直接在 compose 文件中配置环境变量
      # - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      # - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      # - API_SERVER_HOST=0.0.0.0
      # - API_SERVER_KEY=${API_SERVER_KEY}
    command: ["gateway", "start"]

  dashboard:
    image: hermes-agent
    container_name: hermes-dashboard
    restart: unless-stopped
    network_mode: host
    depends_on:
      - gateway
    volumes:
      - ~/.hermes:/opt/data
    environment:
      - HERMES_UID=${HERMES_UID:-10000}
      - HERMES_GID=${HERMES_GID:-10000}
    command: ["dashboard", "--host", "127.0.0.1", "--no-open"]
```

### 2. 创建 .env 文件

```bash
# .env 文件（与 docker-compose.yml 同级）
HERMES_UID=$(id -u)
HERMES_GID=$(id -g)

# 可选：其他环境变量
# OPENROUTER_API_KEY=your_key_here
# TELEGRAM_BOT_TOKEN=your_token_here
```

### 3. 启动服务

```bash
# 启动所有服务
HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down

# 更新并重启
docker compose pull
docker compose up -d --force-recreate
```

## Modal 部署

Modal 提供无服务器的运行环境，可以按需运行 Hermes Agent。

### 前置要求

- Modal 账号：https://modal.com/
- Python 3.11+

### 步骤 1：安装 Modal

```bash
# 安装 Modal
pip install modal

# 认证
modal setup
```

### 步骤 2：创建 Modal 应用

创建 `modal_app.py`：

```python
import modal
import os
from pathlib import Path

# 创建 Modal 应用
app = modal.App("hermes-agent")

# 定义镜像
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "curl", "build-essential")
    .pip_install("uv")
    .run_commands(
        "git clone https://github.com/NousResearch/hermes-agent.git /app",
        "cd /app && uv venv venv && uv pip install -e .[all]",
    )
)

# 定义卷（持久化存储）
volume = modal.Volume.from_name("hermes-data", create_if_missing=True)

# 定义 secrets（从 Modal secrets 中获取）
secrets = [
    modal.Secret.from_name("hermes-secrets"),
]

@app.function(
    image=image,
    volumes={"/data": volume},
    secrets=secrets,
    timeout=3600,
    cpu=2.0,
    memory=4096,
)
def run_hermes(command: str):
    """运行 Hermes 命令"""
    import subprocess
    import os
    
    # 设置环境变量
    os.environ["HERMES_HOME"] = "/data"
    
    # 运行命令
    cmd = ["/app/venv/bin/python", "-m", "hermes"] + command.split()
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }

@app.local_entrypoint()
def main():
    """本地入口点"""
    print("Hermes Agent on Modal")
    print("使用 run_hermes.remote('command') 来运行命令")
    
    # 示例：运行 CLI 帮助
    result = run_hermes.remote("--help")
    print(result["stdout"])
```

### 步骤 3：配置 Modal Secrets

在 Modal Web 界面中创建 secrets：

```bash
# 或者使用 CLI 设置 secrets
modal secret create hermes-secrets \
  OPENROUTER_API_KEY=your_key_here \
  OTHER_ENV_VAR=value
```

### 步骤 4：部署和运行

```bash
# 部署应用
modal deploy modal_app.py

# 运行函数
modal run modal_app.py
```

### 步骤 5：配置终端后端使用 Modal

在 `~/.hermes/config.yaml` 中配置：

```yaml
terminal:
  backend: modal
  modal_image: nikolaik/python-nodejs:python3.11-nodejs20
  cwd: /workspace
  timeout: 180
  lifetime_seconds: 300
```

## Daytona 部署

Daytona 提供云开发环境，可以在其中运行 Hermes Agent。

### 前置要求

- Daytona 账号
- `daytona` CLI 工具

### 步骤 1：安装 Daytona CLI

```bash
# 安装 Daytona
curl -fsSL https://download.daytona.io/get.sh | bash

# 认证
daytona auth
```

### 步骤 2：创建工作区

```bash
# 创建工作区
daytona create hermes-workspace \
  --repo https://github.com/NousResearch/hermes-agent.git \
  --image nikolaik/python-nodejs:python3.11-nodejs20

# 进入工作区
daytona ssh hermes-workspace
```

### 步骤 3：在工作区中安装 Hermes

```bash
# 在工作区中
cd /workspace
./setup-hermes.sh

# 配置
cp .env.example ~/.hermes/.env
nano ~/.hermes/.env

# 运行
hermes
```

### 步骤 4：配置终端后端使用 Daytona

在 `~/.hermes/config.yaml` 中配置：

```yaml
terminal:
  backend: daytona
  daytona_image: nikolaik/python-nodejs:python3.11-nodejs20
  cwd: ~
  timeout: 180
  lifetime_seconds: 300
  container_disk: 10240
```

## 反向代理配置

如果你想通过域名访问 Hermes 网关或仪表盘，可以配置反向代理。

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name hermes.your-domain.com;

    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name hermes.your-domain.com;

    # SSL 证书配置（使用 Let's Encrypt）
    ssl_certificate /etc/letsencrypt/live/hermes.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/hermes.your-domain.com/privkey.pem;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # 仪表盘代理（仅本地访问，需要认证）
    location / {
        proxy_pass http://127.0.0.1:9119;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 认证（使用 HTTP Basic Auth）
        auth_basic "Hermes Dashboard";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }

    # Telegram webhook（如果使用）
    location /telegram {
        proxy_pass http://127.0.0.1:8443;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 速率限制
    limit_req_zone $binary_remote_addr zone=hermes:10m rate=10r/s;
    limit_req zone=hermes;
}
```

### 创建 HTTP Basic Auth 文件

```bash
# 安装 apache2-utils
sudo apt install apache2-utils

# 创建用户和密码
sudo htpasswd -c /etc/nginx/.htpasswd admin
# 输入密码
```

### 获取 SSL 证书

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d hermes.your-domain.com
```

## 生产环境最佳实践

### 1. 安全配置

```yaml
# config.yaml 中的安全配置
terminal:
  backend: docker  # 使用容器隔离
  docker_mount_cwd_to_workspace: false  # 不挂载宿主机目录

# 命令审批（如果实现）
security:
  require_approval_for_dangerous_commands: true
  approved_commands:
    - ls
    - cat
    - echo
```

### 2. 资源限制

```bash
# Docker 资源限制
docker run -d \
  --name hermes \
  --cpus 2 \
  --memory 4g \
  --memory-swap 4g \
  --pids-limit 512 \
  hermes-agent:latest
```

### 3. 日志管理

```yaml
# Docker Compose 日志配置
services:
  gateway:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

### 4. 监控

```bash
# 使用 Prometheus + Grafana 监控
# 或者使用简单的健康检查

# 创建健康检查脚本
cat > /usr/local/bin/hermes-health-check.sh << 'EOF'
#!/bin/bash
if ! systemctl is-active --quiet hermes-gateway; then
    echo "Gateway is not running"
    exit 1
fi
EOF

chmod +x /usr/local/bin/hermes-health-check.sh
```

### 5. 备份策略

```bash
# 创建备份脚本
cat > /usr/local/bin/hermes-backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/hermes"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# 备份配置和数据
tar -czf $BACKUP_DIR/hermes_$DATE.tar.gz \
  ~/.hermes/ \
  --exclude='~/.hermes/logs'

# 保留最近 30 天的备份
find $BACKUP_DIR -name "hermes_*.tar.gz" -mtime +30 -delete
EOF

chmod +x /usr/local/bin/hermes-backup.sh

# 添加到 cron
crontab -e
# 添加：0 2 * * * /usr/local/bin/hermes-backup.sh
```

### 6. 更新策略

```bash
# 创建更新脚本
cat > /usr/local/bin/hermes-update.sh << 'EOF'
#!/bin/bash
set -e

# 备份当前版本
tar -czf /var/backups/hermes/backup_$(date +%Y%m%d_%H%M%S).tar.gz ~/.hermes

# 停止服务
sudo systemctl stop hermes-gateway

# 更新代码
cd ~/hermes-agent
git pull

# 更新依赖
uv sync --frozen

# 运行迁移（如果有）
# hermes migrate

# 启动服务
sudo systemctl start hermes-gateway

echo "Update completed successfully!"
EOF

chmod +x /usr/local/bin/hermes-update.sh
```

## 故障排除

### 常见问题

1. **权限问题**
```bash
# 确保数据目录权限正确
sudo chown -R hermes:hermes ~/.hermes
sudo chmod -R 755 ~/.hermes
```

2. **Docker 容器无法启动**
```bash
# 查看日志
docker logs hermes-gateway

# 检查 UID/GID 映射
echo "UID: $(id -u), GID: $(id -g)"
```

3. **API 调用失败**
```bash
# 检查环境变量
hermes config list

# 验证 API 密钥
echo $OPENROUTER_API_KEY | wc -c  # 应该大于 0
```

4. **端口被占用**
```bash
# 查看端口使用
sudo netstat -tlnp | grep 9119

# 或使用 ss
sudo ss -tlnp | grep 9119
```

### 获取帮助

如果遇到问题：
- 查看日志：`journalctl -u hermes-gateway -f`
- 运行诊断：`hermes doctor`
- 检查配置：`hermes config list`
- 访问 GitHub Issues：https://github.com/NousResearch/hermes-agent/issues

## 总结

本指南涵盖了多种部署方式：

- **本地部署** - 适合开发和测试
- **云端服务器** - 适合生产环境
- **Docker** - 提供隔离和一致性
- **Modal** - 无服务器，按需付费
- **Daytona** - 云开发环境

选择适合你需求的部署方式，并遵循生产环境最佳实践以确保安全和稳定。
