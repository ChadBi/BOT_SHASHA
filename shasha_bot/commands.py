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
    run_mentioned_text,
    run_mentioned_with_image,
    run_mentioned_with_reply,
    run_random_chitchat,
    run_reply_callback,
)

try:
    from .commands_custom import CUSTOM_COMMANDS
except Exception:
    CUSTOM_COMMANDS = []


def build_commands() -> List[Command]:
    """命令匹配顺序：从上到下，先匹配先执行。

    你后续加功能：优先在 commands_custom.py 里加。
    """

    commands: List[Command] = []

    # 0) 回调必须最优先（reply_check_* 依赖 pending_requests）
    commands.append(
        FunctionCommand(
            name="reply_callback",
            _match=lambda ctx: ctx.is_reply_callback,
            _run=run_reply_callback,
        )
    )

    # 1) 你的自定义命令（建议放前面，优先级最高）
    commands.extend(CUSTOM_COMMANDS)

    # 2) 内置逻辑（保持之前行为）
    commands.append(
        FunctionCommand(
            name="mentioned_with_image",
            _match=lambda ctx: ctx.is_message_event and (not ctx.is_self_message()) and ctx.is_mentioned and bool(ctx.img_url) and ctx.is_image_enabled(),
            _run=run_mentioned_with_image,
        )
    )

    commands.append(
        FunctionCommand(
            name="mentioned_with_reply",
            _match=lambda ctx: ctx.is_message_event and (not ctx.is_self_message()) and ctx.is_mentioned and bool(ctx.reply_id) and not ctx.img_url,
            _run=run_mentioned_with_reply,
        )
    )

    commands.append(
        FunctionCommand(
            name="mentioned_text",
            _match=lambda ctx: ctx.is_message_event and (not ctx.is_self_message()) and ctx.is_mentioned and (not ctx.img_url) and (not ctx.reply_id),
            _run=run_mentioned_text,
        )
    )

    commands.append(
        FunctionCommand(
            name="random_chitchat",
            _match=lambda ctx: ctx.is_message_event and (not ctx.is_self_message()) and (not ctx.is_mentioned) and (not ctx.img_url) and ctx.random_reply_chance() > 0,
            _run=run_random_chitchat,
        )
    )

    return commands


__all__ = ["build_commands", "dispatch"]
