"""@机器人纯文本处理器。

处理 @机器人 + 纯文本消息的场景。
集成记忆模块进行增强对话。
"""

import logging

from ..router import BotContext
from ..memory.prompt import build_system_context, build_chat_messages

logger = logging.getLogger(__name__)


class TextHandler:
    """处理 @机器人的纯文本消息。"""

    async def handle(self, ctx: BotContext) -> bool:
        """处理 @机器人的纯文本消息。

        返回:
            是否已处理
        """
        question = ctx.text or "你叫我干嘛？"
        user_id = str(ctx.user_id) if ctx.user_id else None

        # 如果有记忆模块，使用增强对话
        if ctx.services.memory and user_id:
            try:
                memory = ctx.services.memory

                # 0) 识别用户情绪（优先 LLM，失败自动降级）
                user_emotion = await memory.emotion_recognizer.recognize_async(question)

                # 1) 记录"用户本轮输入"到 STM（仅自然语言对话才写入）
                await memory.append_to_stm(
                    user_id=user_id,
                    role="user",
                    text=question,
                    meta={
                        "message_type": ctx.message_type,
                        "group_id": ctx.group_id,
                        "trigger": "mentioned_text",
                        "emotion": user_emotion.label,
                    },
                )

                # 2. 获取用户状态和关系
                user_state = await memory.get_user_state(user_id)
                relation = await memory.get_relation(user_id)
                bot_emotion = memory.get_bot_emotion()

                # 3. 构建系统上下文
                system_prompt = build_system_context(
                    user_state=user_state,
                    relation=relation,
                    user_emotion=user_emotion,
                    bot_vad=bot_emotion,
                    base_system_prompt=ctx.settings.system_prompt,
                )

                # 4. 获取历史对话并构造多轮 messages
                stm = memory.get_stm(user_id)
                messages = build_chat_messages(
                    stm=stm,
                    current_question=question,
                    system_prompt=system_prompt,
                    max_history=10,
                )

                # 5. 调用 LLM（多轮）
                reply_text = await ctx.services.deepseek.ask_with_messages(messages)

                # 6. 记录机器人回复到 STM
                await memory.append_to_stm(
                    user_id=user_id,
                    role="assistant",
                    text=reply_text,
                    meta={"emotion": user_emotion.label},
                )

                # 7. 更新关系和情绪
                await memory.update_relation_on_interaction(user_id)
                bot_state = await memory.update_bot_emotion(user_emotion, user_id)
                logger.info(
                    f"[bot_emotion] tone={bot_state.get_suggested_tone()} "
                    f"V={bot_state.V:.2f} A={bot_state.A:.2f} D={bot_state.D:.2f}"
                )

                if user_emotion.label in ("angry", "disgust") and user_emotion.intensity > 0.6:
                    await memory.update_relation_on_negative_emotion(user_id, user_emotion.intensity)

                # 8. 异步任务：LTM 提取和人格分析（不阻塞回复）
                try:
                    await memory.extract_ltm_from_stm(user_id)
                    await memory.maybe_update_personality(user_id, ctx.services.deepseek)
                except Exception as bg_err:
                    logger.error(f"[chat] 后台任务失败: {bg_err}")

                logger.info(f"[chat] mentioned_text user={user_id} emo={user_emotion.label} reply_len={len(reply_text)}")

            except Exception as e:
                logger.error(f"[chat] 记忆模块对话失败，降级到普通模式: {e}")
                reply_text = await ctx.services.deepseek.ask(question)
        else:
            # 无记忆模块，使用普通模式
            reply_text = await ctx.services.deepseek.ask(question)

        await ctx.send_text(reply_text, quote=False)
        return True
