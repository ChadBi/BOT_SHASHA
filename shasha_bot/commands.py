from __future__ import annotations

"""命令装配（决定优先级）。

build_commands() 返回一个按优先级排列的命令列表：
- 从上到下匹配，先命中先执行
- CUSTOM_COMMANDS 会被插在内置逻辑之前

你以后新增功能：优先在 commands_custom.py 里加。
"""

from typing import List

from .router import (
    Command,
    FunctionCommand,
    dispatch,
)

# 导入新的处理器
from .handlers.text import TextHandler
from .handlers.image import ImageHandler
from .handlers.reply import ReplyHandler, ReplyCallbackHandler
from .handlers.chitchat import ChitchatHandler

# 实例化处理器
_text_handler = TextHandler()
_image_handler = ImageHandler()
_reply_handler = ReplyHandler()
_reply_callback_handler = ReplyCallbackHandler()
_chitchat_handler = ChitchatHandler()

try:
    from .commands_custom import CUSTOM_COMMANDS
except Exception:
    CUSTOM_COMMANDS = []


def build_commands() -> List[Command]:
    """命令匹配顺序：从上到下，先匹配先执行。

    你后续加功能：优先在 commands_custom.py 里加。
    """

    commands: List[Command] = []

    # 0) 回复回调必须最优先（reply_check_* 依赖 pending_requests）
    commands.append(
        FunctionCommand(
            name="reply_callback",
            _match=lambda ctx: ctx.is_reply_callback,
            _run=_reply_callback_handler.handle,
        )
    )

    # 1) 你的自定义命令（建议放前面，优先级最高）
    commands.extend(CUSTOM_COMMANDS)

    # 2) @机器人 + 图片
    commands.append(
        FunctionCommand(
            name="mentioned_with_image",
            _match=lambda ctx: ctx.is_message_event and (not ctx.is_self_message()) and ctx.is_mentioned and bool(ctx.img_url) and ctx.is_image_enabled(),
            _run=_image_handler.handle,
        )
    )

    # 3) @机器人 + 回复消息（发送 get_msg 请求）
    commands.append(
        FunctionCommand(
            name="mentioned_with_reply",
            _match=lambda ctx: ctx.is_message_event and (not ctx.is_self_message()) and ctx.is_mentioned and bool(ctx.reply_id) and not ctx.img_url,
            _run=_reply_handler.handle,
        )
    )

    # 4) @机器人 + 纯文本
    commands.append(
        FunctionCommand(
            name="mentioned_text",
            _match=lambda ctx: ctx.is_message_event and (not ctx.is_self_message()) and ctx.is_mentioned and (not ctx.img_url) and (not ctx.reply_id),
            _run=_text_handler.handle,
        )
    )

    # 5) 随机闲聊（非 @ 消息）
    commands.append(
        FunctionCommand(
            name="random_chitchat",
            _match=lambda ctx: ctx.is_message_event and (not ctx.is_self_message()) and (not ctx.is_mentioned) and (not ctx.img_url) and ctx.random_reply_chance() > 0,
            _run=_chitchat_handler.handle,
        )
    )

    return commands


__all__ = ["build_commands", "dispatch"]
