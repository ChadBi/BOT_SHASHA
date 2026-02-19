"""回复消息处理器。

处理回复消息的场景（用户回复某条消息，@机器人）。
需要先调用 get_msg API 获取原消息内容，再进行回复。
"""

import json
import logging

from ..router import BotContext, ReplyContext
from ..cq import extract_image_url, normalize_user_text

logger = logging.getLogger(__name__)


class ReplyHandler:
    """处理回复消息。"""

    async def handle(self, ctx: BotContext) -> bool:
        """处理回复消息。

        流程：
        1. 发送 get_msg 请求获取原消息
        2. 把当前上下文塞进 pending_requests
        3. 等待回调（由 callback.py 处理）

        返回:
            是否已处理（返回 False，因为是异步回调模式）
        """
        if ctx.message_id is None or not ctx.reply_id:
            return False

        logger.info(f"[reply] 检测到回复消息，正在获取原消息内容 (ID: {ctx.reply_id})...")
        echo_id = f"reply_check_{ctx.message_id}"
        ctx.pending_requests[echo_id] = ReplyContext(
            user_id=ctx.user_id,
            group_id=ctx.group_id,
            message_type=ctx.message_type,
            message_id=ctx.message_id,
            raw_msg=ctx.raw_msg,
        )
        req = {"action": "get_msg", "params": {"message_id": ctx.reply_id}, "echo": echo_id}
        await ctx.send_payload(req)
        return True


class ReplyCallbackHandler:
    """处理回复消息的回调（get_msg 响应）。"""

    async def handle(self, ctx: BotContext) -> bool:
        """处理 get_msg 响应。

        返回:
            是否已处理
        """
        echo_id = ctx.event.get("echo")
        saved = ctx.pending_requests.pop(echo_id, None)
        if not saved:
            return False

        logger.info(f"[reply] 收到 get_msg 响应: {echo_id}")
        msg_data = ctx.event.get("data", {})
        target_msg = msg_data.get("raw_message") or str(msg_data.get("message", ""))
        user_id = str(saved.user_id) if saved.user_id else None

        target_img_url = extract_image_url(target_msg)
        user_msg_clean = normalize_user_text(saved.raw_msg)

        if target_img_url:
            logger.info("[reply] 在被回复的消息中找到了图片！")

            if user_msg_clean.startswith("编辑="):
                edit_prompt = user_msg_clean[3:].strip()
                if not edit_prompt:
                    reply_text = "请在'编辑='后面加上你的修图指令哦~"
                else:
                    reply_text = await ctx.services.image_edit.edit(target_img_url, edit_prompt)
            else:
                reply_text = await ctx.services.vision.ask(target_img_url)
        else:
            logger.info("[reply] 被回复的消息里没有图片，转为普通文本回复...")
            user_question = user_msg_clean or "（盯着你回复的消息看）"
            full_prompt = f"我回复了消息：'{target_msg}'。\n我的评论是：{user_question}"
            reply_text = await ctx.services.deepseek.ask(full_prompt)

        # 记录到 STM（如果有记忆模块）
        if ctx.services.memory and user_id:
            try:
                memory = ctx.services.memory
                trigger_type = "reply_with_image" if target_img_url else "reply_text"

                # 识别用户情绪
                try:
                    emotion_text = user_msg_clean or "（回复了一条消息）"
                    user_emotion = await memory.emotion_recognizer.recognize_async(emotion_text)
                except Exception as emo_err:
                    logger.error(f"[emotion] 回复场景情绪识别失败: {emo_err}")
                    user_emotion = None

                # 记录用户回复行为
                await memory.append_to_stm(
                    user_id=user_id,
                    role="user",
                    text=f"[回复消息] {user_msg_clean}" if user_msg_clean else f"[回复消息: {target_msg[:30]}...]",
                    meta={
                        "trigger": trigger_type,
                        "has_image": bool(target_img_url),
                        "emotion": getattr(user_emotion, "label", None),
                    },
                )

                # 记录机器人回复
                await memory.append_to_stm(
                    user_id=user_id,
                    role="assistant",
                    text=reply_text,
                    meta={"trigger": trigger_type},
                )

                await memory.update_relation_on_interaction(user_id)

                # 更新并打印机器人情绪
                if user_emotion is not None:
                    bot_state = await memory.update_bot_emotion(user_emotion, user_id)
                    logger.info(
                        f"[bot_emotion] tone={bot_state.get_suggested_tone()} "
                        f"V={bot_state.V:.2f} A={bot_state.A:.2f} D={bot_state.D:.2f}"
                    )
                logger.info(f"[chat] {trigger_type} user={user_id} reply_len={len(reply_text)}")
            except Exception as e:
                logger.error(f"[chat] 回复场景记忆写入失败: {e}")

        payload = {
            "action": "send_msg",
            "params": {
                "message_type": saved.message_type,
                "message": f"[CQ:reply,id={saved.message_id}] {reply_text}",
            },
        }
        if saved.message_type == "group":
            payload["params"]["group_id"] = saved.group_id
        else:
            payload["params"]["user_id"] = saved.user_id

        await ctx.send_payload(payload)
        return True
