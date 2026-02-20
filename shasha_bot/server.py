"""WebSocket Server 启动封装。

这里仅负责：开 websockets server，并把连接交给 handler.handle_message。
"""

from __future__ import annotations

import asyncio
import logging

import websockets

from .handler import handle_message
from .settings import BotSettings

logger = logging.getLogger(__name__)


async def run_server(settings: BotSettings) -> None:
    """启动 WebSocket Server，并永久阻塞运行。"""
    logger.info("鲨鲨启动中 ws://%s:%s", settings.host, settings.port)

    async def _handler(ws):
        # 每条 WebSocket 连接都用同一套 settings
        await handle_message(ws, settings)

    async with websockets.serve(_handler, settings.host, settings.port):
        await asyncio.Future()
