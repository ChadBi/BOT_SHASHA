"""持久化存储模块。

职责：
- 异步读写 JSON 文件
- 使用线程池避免阻塞事件循环
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# 全局线程池（避免每次创建）
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="memory_io")


def _sync_read_json(path: Path) -> Dict[str, Any]:
    """同步读取 JSON 文件（在线程池中调用）。"""
    try:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("读取 %s 失败: %s", path, e)
        return {}


def _sync_write_json(path: Path, data: Dict[str, Any]) -> bool:
    """同步写入 JSON 文件（在线程池中调用）。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        logger.warning("写入 %s 失败: %s", path, e)
        return False


async def async_read_json(path: Path) -> Dict[str, Any]:
    """异步读取 JSON 文件。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _sync_read_json, path)


async def async_write_json(path: Path, data: Dict[str, Any]) -> bool:
    """异步写入 JSON 文件。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _sync_write_json, path, data)


class Storage:
    """存储管理器（管理用户数据目录）。"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _user_file(self, user_id: str) -> Path:
        """用户数据文件路径。"""
        return self.base_dir / "users" / f"{user_id}.json"

    def _bot_state_file(self) -> Path:
        """机器人全局状态文件路径。"""
        return self.base_dir / "bot_state.json"

    async def load_user(self, user_id: str) -> Dict[str, Any]:
        """加载用户数据。"""
        return await async_read_json(self._user_file(user_id))

    async def save_user(self, user_id: str, data: Dict[str, Any]) -> bool:
        """保存用户数据。"""
        return await async_write_json(self._user_file(user_id), data)

    async def load_bot_state(self) -> Dict[str, Any]:
        """加载机器人全局状态。"""
        return await async_read_json(self._bot_state_file())

    async def save_bot_state(self, data: Dict[str, Any]) -> bool:
        """保存机器人全局状态。"""
        return await async_write_json(self._bot_state_file(), data)
