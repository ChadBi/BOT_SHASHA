# 鲨鲨机器人部署文档

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/ChadBi/BOT_SHASHA.git
cd BOT_SHASHA

# 2. 安装 uv (如果未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.cargo/env

# 3. 安装依赖
uv sync

# 4. 配置配置文件
cp config/bot_settings.example.json config/bot_settings.json
# 编辑 config/bot_settings.json 填入你的 API Key

# 5. 运行
uv run python run_bot.py
```

---

## 持久运行（生产环境）

### 方案一：Systemd 服务（推荐，适用于 Linux）

#### 1. 创建服务文件

```bash
sudo nano /etc/systemd/system/shasha-bot.service
```

粘贴以下内容（**修改 `WorkingDirectory` 和 `ExecStart` 为你的实际路径**）：

```ini
[Unit]
Description=Shasha Bot - QQ 机器人
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/BOT_SHASHA
Environment="PATH=/home/your-username/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/your-username/.local/bin/uv run python run_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=shasha-bot

# 安全加固
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

#### 2. 启用并启动服务

```bash
# 重载 systemd
sudo systemctl daemon-reload

# 启用开机自启
sudo systemctl enable shasha-bot

# 启动服务
sudo systemctl start shasha-bot

# 查看状态
sudo systemctl status shasha-bot
```

#### 3. 常用命令

```bash
# 查看日志
sudo journalctl -u shasha-bot -f

# 查看最近 100 行
sudo journalctl -u shasha-bot -n 100

# 重启服务
sudo systemctl restart shasha-bot

# 停止服务
sudo systemctl stop shasha-bot

# 禁用开机自启
sudo systemctl disable shasha-bot
```

---

### 方案二：TMUX 后台运行（简单，适用于开发）

```bash
# 1. 安装 tmux
sudo apt install tmux  # Ubuntu/Debian
sudo yum install tmux  # CentOS/RHEL

# 2. 创建 tmux 会话
tmux new -s shasha-bot

# 3. 运行机器人
uv run python run_bot.py

# 4. 分离会话（保持后台运行）
# 按 Ctrl+B, 然后按 D

# 5. 重新连接
tmux attach -t shasha-bot

# 6. 查看所有会话
tmux ls
```

---

### 方案三：Screen 后台运行（备选）

```bash
# 1. 安装 screen
sudo apt install screen

# 2. 创建 screen 会话
screen -S shasha-bot

# 3. 运行机器人
uv run python run_bot.py

# 4. 分离会话
# 按 Ctrl+A, 然后按 D

# 5. 重新连接
screen -r shasha-bot

# 6. 查看所有会话
screen -ls
```

---

### 方案四：Docker 容器化运行（高级）

#### 1. 创建 Dockerfile

项目根目录下创建 `Dockerfile`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 复制项目文件
COPY pyproject.toml uv.lock ./
COPY shasha_bot/ ./shasha_bot/
COPY run_bot.py ./

# 安装依赖
RUN uv sync --frozen

# 运行
CMD ["uv", "run", "python", "run_bot.py"]
```

#### 2. 构建并运行

```bash
# 构建镜像
docker build -t shasha-bot .

# 运行容器
docker run -d \
  --name shasha-bot \
  --restart always \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/shasha_bot/memory_data:/app/shasha_bot/memory_data \
  shasha-bot
```

#### 3. 常用命令

```bash
# 查看日志
docker logs -f shasha-bot

# 重启
docker restart shasha-bot

# 停止
docker stop shasha-bot

# 删除
docker rm shasha-bot
```

---

## 配置文件说明

### `config/bot_settings.json`

```json
{
  "host": "127.0.0.1",
  "port": 8095,

  "deepseek_api_key": "你的 DeepSeek API Key",
  "zhipu_api_key": "你的智谱 API Key",
  "aliyun_api_key": "你的阿里云 DashScope Key",
  "siliconflow_api_key": "你的 SiliconFlow API Key",

  "enable_memory": true,
  "enable_rate_limit": true,

  "admin_user_ids": [你的 QQ 号],

  "log_level": "INFO"
}
```

### `config/group_settings.json`

群运行配置，不需要可以删除。

---

## 日志管理

### Systemd 日志

```bash
# 查看今天的日志
sudo journalctl -u shasha-bot --since today

# 查看最近 1 小时
sudo journalctl -u shasha-bot --since "1 hour ago"

# 清空日志（谨慎使用）
sudo journalctl --rotate
sudo journalctl --vacuum-time=1d
```

### 应用日志

日志文件位于 `logs/` 目录，可以配置日志轮转：

```bash
sudo nano /etc/logrotate.d/shasha-bot
```

```
/path/to/BOT_SHASHA/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 your-username your-username
}
```

---

## 常见问题

### 1. 服务启动失败

```bash
# 查看详细错误
sudo journalctl -u shasha-bot -n 50 --no-pager

# 检查配置
uv run python -c "from shasha_bot.settings import load_settings; load_settings()"
```

### 2. 依赖安装失败

```bash
# 清理缓存重新安装
rm -rf .venv
uv sync
```

### 3. 端口被占用

```bash
# 查看占用端口的进程
sudo lsof -i :8095

# 修改 config/bot_settings.json 中的 port
```

### 4. 内存不足

```bash
# 查看内存使用
free -h
top

# 减少 memory 模块的缓存
# 在 config/bot_settings.json 中设置:
# "stm_max_turns": 10
```

### 5. 网络问题

```bash
# 测试 API 连通性
curl https://api.deepseek.com

# 检查防火墙
sudo ufw status
```

---

## 更新机器人

```bash
# 1. 进入项目目录
cd /path/to/BOT_SHASHA

# 2. 拉取最新代码
git pull

# 3. 更新依赖
uv sync

# 4. 重启服务
sudo systemctl restart shasha-bot

# 5. 查看日志确认启动成功
sudo journalctl -u shasha-bot -f
```

---

## 监控和告警

### 添加健康检查

创建 `healthcheck.py`：

```python
#!/usr/bin/env python
"""健康检查脚本。"""

import sys
import socket

def check_port(host: str, port: int) -> bool:
    """检查端口是否可连接。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        sock.close()
        return True
    except Exception:
        return False

if __name__ == "__main__":
    if check_port("127.0.0.1", 8095):
        print("OK")
        sys.exit(0)
    else:
        print("FAIL")
        sys.exit(1)
```

### 添加到 crontab

```bash
crontab -e
```

```
*/5 * * * * /path/to/BOT_SHASHA/venv/bin/python /path/to/BOT_SHASHA/healthcheck.py || sudo systemctl restart shasha-bot
```

---

## 备份数据

```bash
# 备份记忆数据
tar -czf shasha_memory_backup_$(date +%Y%m%d).tar.gz shasha_bot/memory_data/

# 备份配置
tar -czf shasha_config_backup_$(date +%Y%m%d).tar.gz config/
```

---

## 卸载

```bash
# 停止服务
sudo systemctl stop shasha-bot
sudo systemctl disable shasha-bot

# 删除服务文件
sudo rm /etc/systemd/system/shasha-bot.service
sudo systemctl daemon-reload

# 删除项目
rm -rf /path/to/BOT_SHASHA
```

---

## 技术支持

遇到问题可以：
1. 查看日志定位问题
2. 检查配置文件格式
3. 确认 API Key 有效
4. 检查网络连接
5. 查看 GitHub Issues
