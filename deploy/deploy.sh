#!/bin/bash
# 鲨鲨机器人一键部署脚本 (Linux)
# 使用方法：bash deploy.sh

set -e

echo "======================================"
echo "  鲨鲨机器人部署脚本"
echo "======================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否已安装 uv
check_uv() {
    if command -v uv &> /dev/null; then
        echo -e "${GREEN}✓ uv 已安装${NC}"
    else
        echo -e "${YELLOW}! uv 未安装，正在安装...${NC}"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        source ~/.cargo/env 2>/dev/null || true
        export PATH="$HOME/.local/bin:$PATH"
    fi
}

# 检查 Python
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version)
        echo -e "${GREEN}✓ $PYTHON_VERSION${NC}"
    else
        echo -e "${RED}✗ Python3 未安装${NC}"
        exit 1
    fi
}

# 安装依赖
install_deps() {
    echo -e "${YELLOW}! 安装依赖...${NC}"
    uv sync
    echo -e "${GREEN}✓ 依赖安装完成${NC}"
}

# 配置配置文件
setup_config() {
    if [ ! -f "config/bot_settings.json" ]; then
        echo -e "${YELLOW}! 创建配置文件...${NC}"
        cp config/bot_settings.example.json config/bot_settings.json
        echo -e "${GREEN}✓ 配置文件已创建：config/bot_settings.json${NC}"
        echo -e "${YELLOW}! 请编辑 config/bot_settings.json 填入你的 API Key${NC}"
    else
        echo -e "${GREEN}✓ 配置文件已存在${NC}"
    fi
}

# 创建 systemd 服务
setup_systemd() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}! 非 root 用户，跳过 systemd 配置${NC}"
        echo -e "${YELLOW}! 如需配置 systemd 服务，请运行：sudo bash $0 systemd${NC}"
        return
    fi

    echo -e "${YELLOW}! 配置 systemd 服务...${NC}"

    # 获取当前用户
    CURRENT_USER=${SUDO_USER:-$USER}
    HOME_DIR=$(eval echo ~$CURRENT_USER)
    WORK_DIR=$(pwd)

    # 创建服务文件
    cat > /etc/systemd/system/shasha-bot.service << EOF
[Unit]
Description=Shasha Bot - QQ 机器人
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$WORK_DIR
Environment="PATH=$HOME_DIR/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$HOME_DIR/.local/bin/uv run python run_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=shasha-bot

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

    # 启用服务
    systemctl daemon-reload
    systemctl enable shasha-bot

    echo -e "${GREEN}✓ systemd 服务已配置${NC}"
    echo -e "${YELLOW}! 启动服务：sudo systemctl start shasha-bot${NC}"
    echo -e "${YELLOW}! 查看状态：sudo systemctl status shasha-bot${NC}"
    echo -e "${YELLOW}! 查看日志：sudo journalctl -u shasha-bot -f${NC}"
}

# 主函数
main() {
    check_python
    check_uv
    install_deps
    setup_config

    echo ""
    echo "======================================"
    echo -e "${GREEN}  部署完成！${NC}"
    echo "======================================"
    echo ""
    echo "下一步："
    echo "  1. 编辑 config/bot_settings.json 填入 API Key"
    echo "  2. 运行：uv run python run_bot.py"
    echo ""
    echo "持久运行："
    echo "  方案 1 (推荐): sudo bash $0 systemd"
    echo "  方案 2 (简单): tmux new -s shasha && uv run python run_bot.py (然后 Ctrl+B, D)"
    echo ""
}

# 处理参数
case "${1:-}" in
    systemd)
        setup_systemd
        ;;
    *)
        main
        ;;
esac
