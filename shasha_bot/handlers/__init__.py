"""业务处理器。

按消息类型拆分业务逻辑：
- text.py: @机器人纯文本处理
- image.py: @机器人图片处理
- reply.py: 回复消息处理
- chitchat.py: 随机闲聊处理
- callback.py: 回调处理（get_msg 响应等）

每个处理器实现 handle(ctx) 方法，返回是否已处理。
"""

from typing import Protocol

from ..router import BotContext


class Handler(Protocol):
    """处理器协议。"""

    async def handle(self, ctx: BotContext) -> bool:
        """处理消息，返回是否已处理。"""
        ...


__all__ = ["Handler"]
