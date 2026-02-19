"""@机器人+图片处理器。

处理 @机器人 + 图片消息的场景。
集成记忆模块记录用户发图行为和评价。
"""

import logging

from ..router import BotContext

logger = logging.getLogger(__name__)


class ImageHandler:
    """处理 @机器人 + 图片消息。"""

    async def handle(self, ctx: BotContext) -> bool:
        """处理 @机器人 + 图片消息。

        返回:
            是否已处理
        """
        user_id = str(ctx.user_id) if ctx.user_id else None
        img_description = ctx.text or "看看这张图"

        # 调用视觉模型
        reply_text = await ctx.services.vision.ask(ctx.img_url or "")

        # 记录到 STM（如果有记忆模块）
        if ctx.services.memory and user_id:
            try:
                memory = ctx.services.memory

                # 识别用户情绪（用用户随图附带的文字/描述）
                user_emotion = await memory.emotion_recognizer.recognize_async(img_description)

                # 记录用户发图行为
                await memory.append_to_stm(
                    user_id=user_id,
                    role="user",
                    text=f"[发送图片] {img_description}",
                    meta={
                        "trigger": "mentioned_with_image",
                        "has_image": True,
                        "emotion": user_emotion.label,
                    },
                )

                # 记录机器人回复
                await memory.append_to_stm(
                    user_id=user_id,
                    role="assistant",
                    text=reply_text,
                    meta={"trigger": "mentioned_with_image"},
                )

                await memory.update_relation_on_interaction(user_id)

                # 更新并打印机器人情绪
                bot_state = await memory.update_bot_emotion(user_emotion, user_id)
                logger.info(
                    f"[bot_emotion] tone={bot_state.get_suggested_tone()} "
                    f"V={bot_state.V:.2f} A={bot_state.A:.2f} D={bot_state.D:.2f}"
                )
                logger.info(f"[chat] mentioned_with_image user={user_id} reply_len={len(reply_text)}")
            except Exception as e:
                logger.error(f"[chat] 图片场景记忆写入失败: {e}")

        await ctx.send_text(reply_text, quote=True)
        return True
