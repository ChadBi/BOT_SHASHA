"""启动入口。

本项目作为 NapCat/OneBot 的 WebSocket Server：
- NapCat 连接到 ws://127.0.0.1:8095/（见 runtime/config/bot.json）
- 本脚本启动 server 并把事件交给 shasha_bot 处理
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# 允许两种运行方式：
# 1) 从仓库根目录：python .\BOT\run_bot.py
# 2) 被 import：import BOT.run_bot
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from shasha_bot.server import run_server
from shasha_bot.settings import load_settings


def main() -> None:
    """读取配置并启动 WebSocket Server。"""
    default_config = Path(__file__).resolve().parent / "config" / "bot_settings.json"
    if not default_config.exists():
        raise FileNotFoundError(
            f"缺少配置文件: {default_config}. 请复制 BOT/config/bot_settings.example.json 为 bot_settings.json 并填写 key。"
        )

    settings = load_settings(str(default_config))
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    asyncio.run(run_server(settings))


if __name__ == "__main__":
    main()
