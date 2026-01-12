from __future__ import annotations

"""消息处理主循环。

职责：
- 接收 NapCat/OneBot 推送的事件（JSON）
- 构建 BotContext（把常用字段/解析结果挂上去）
- 调用 commands + router 进行“按优先级匹配并执行”

注意：
- 以后加新功能，优先改 commands_custom.py，而不是在这里堆 if。
"""

import json
from typing import Dict

import websockets

from .settings import BotSettings
from .ai import DeepSeekText, ZhipuVision, AliyunImageEdit
from .router import BotContext, ReplyContext, Services, dispatch
from .commands import build_commands


async def handle_message(websocket, settings: BotSettings) -> None:
    """处理单条 WebSocket 连接上的所有事件。"""
    print("✅ 连接成功！")

    # 统一在这里初始化外部服务（避免每条消息重复创建客户端）
    deepseek = DeepSeekText(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        system_prompt=settings.system_prompt,
        temperature=settings.temperature,
        max_tokens=settings.max_text_tokens,
    )
    vision = ZhipuVision(
        api_key=settings.zhipu_api_key,
        system_prompt=settings.system_prompt,
        vision_prompt=settings.vision_prompt,
        temperature=settings.temperature,
    )
    image_edit = AliyunImageEdit(api_key=settings.aliyun_api_key)

    # services：给命令/路由使用的“依赖注入容器”
    services = Services(deepseek=deepseek, vision=vision, image_edit=image_edit)
    # commands：按顺序匹配，先命中先执行
    commands = build_commands()
    pending_requests: Dict[str, ReplyContext] = {}

    try:
        async for message in websocket:
            event = json.loads(message)

            # 构建上下文：解析 CQ 码、判断是否 @、是否含图、是否是 reply callback 等
            ctx = BotContext.from_event(
                websocket=websocket,
                event=event,
                settings=settings,
                services=services,
                pending_requests=pending_requests,
            )

            if ctx.is_message_event and ctx.is_self_message():
                # 忽略机器人自己发的消息，避免自我触发
                continue

            if ctx.is_message_event:
                print(f"📩 [{ctx.user_id}][{ctx.message_type}] 收到: {ctx.raw_msg}")

            # 交给路由系统：根据命令优先级做匹配与执行
            await dispatch(commands, ctx)

    except websockets.exceptions.ConnectionClosed:
        print("⚠️ 连接断开")
