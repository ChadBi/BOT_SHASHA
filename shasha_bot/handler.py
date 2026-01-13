from __future__ import annotations

"""消息处理主循环。

职责：
- 接收 NapCat/OneBot 推送的事件（JSON）
- 构建 BotContext（把常用字段/解析结果挂上去）
- 调用 commands + router 进行"按优先级匹配并执行"
- 管理记忆与情绪状态

注意：
- 以后加新功能，优先改 commands_custom.py，而不是在这里堆 if。
"""

import json
import logging
from typing import Dict, Optional

import websockets

from .settings import BotSettings
from .ai import DeepSeekText, ZhipuVision, AliyunImageEdit, SiliconFlowEmotionClient
from .router import BotContext, ReplyContext, Services, dispatch
from .commands import build_commands
from .memory import MemoryManager, MemoryConfig

logger = logging.getLogger(__name__)


async def handle_message(websocket, settings: BotSettings) -> None:
    """处理单条 WebSocket 连接上的所有事件。"""
    print("✅ 连接成功！")

    # 初始化记忆管理器（如果启用）
    memory_manager: Optional[MemoryManager] = None
    if settings.enable_memory:
        memory_config = MemoryConfig()
        memory_config.STM_MAX_TURNS = settings.stm_max_turns
        memory_config.PERSONALITY_UPDATE_MIN_MSGS = settings.personality_update_min_msgs
        memory_config.PERSONALITY_UPDATE_COOLDOWN_HOURS = settings.personality_update_cooldown_hours
        memory_config.EMOTION_DECAY_ALPHA = settings.emotion_decay_alpha
        memory_config.MAX_SELF_DESCRIPTIONS = settings.max_self_descriptions
        memory_manager = MemoryManager(config=memory_config)
        
        # 如果配置了 SiliconFlow API key，初始化 LLM 情绪识别
        if settings.siliconflow_api_key:
            emotion_client = SiliconFlowEmotionClient(api_key=settings.siliconflow_api_key)
            memory_manager.emotion_recognizer.set_llm_client(emotion_client)
            print("[memory] 记忆模块已启用（含 LLM 情绪识别）")
        else:
            print("[memory] 记忆模块已启用（规则情绪识别）")

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

    # services：给命令/路由使用的"依赖注入容器"
    services = Services(deepseek=deepseek, vision=vision, image_edit=image_edit, memory=memory_manager)
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

                # 记忆写入仅在“自然语言对话”路径中进行：
                # - @我 + 文字（router.run_mentioned_text）
                # - 随机闲聊触发（router.run_random_chitchat）
                # 常规命令（昵称=/自述=/查看记忆/菜单等）不计入对话历史。

            # 交给路由系统：根据命令优先级做匹配与执行
            await dispatch(commands, ctx)

    except websockets.exceptions.ConnectionClosed:
        print("⚠️ 连接断开")
