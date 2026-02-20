"""命令路由与上下文（扩展功能的核心）。

这套机制的目标：
- 把“很多 if/elif”变成“按优先级排列的命令列表”
- 以后新增功能：只需要添加一个 Command（见 commands_custom.py）

关键概念：
- BotContext：一条事件的“上下文”，包含解析后的字段、AI 服务、发送消息方法
- Command：匹配(match) + 执行(run) 的可插拔单元
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from collections import deque
from typing import Any, Awaitable, Callable, Deque, Dict, Iterable, List, Optional, Protocol

from .cq import extract_image_url, extract_reply_id, contains_at, normalize_user_text
from .memory.prompt import build_system_context, build_chat_messages

logger = logging.getLogger(__name__)
from .settings import BotSettings


@dataclass
class ReplyContext:
    """用于异步回调场景：保存 `get_msg` 请求发出时的上下文。"""
    user_id: int | None
    group_id: int | None
    message_type: str
    message_id: int
    raw_msg: str
    created_at: float = 0.0




class SimpleRateLimiter:
    """简单滑动窗口限流（用户/群）。"""

    def __init__(self, *, enabled: bool, window_seconds: int, user_max_calls: int, group_max_calls: int):
        self.enabled = enabled
        self.window_seconds = max(1, int(window_seconds))
        self.user_max_calls = max(1, int(user_max_calls))
        self.group_max_calls = max(1, int(group_max_calls))
        self._user_calls: Dict[str, Deque[float]] = {}
        self._group_calls: Dict[str, Deque[float]] = {}

    def _evict_old(self, q: Deque[float], now: float) -> None:
        threshold = now - self.window_seconds
        while q and q[0] < threshold:
            q.popleft()

    def _allow(self, store: Dict[str, Deque[float]], key: str, limit: int) -> bool:
        now = time.time()
        q = store.setdefault(key, deque())
        self._evict_old(q, now)
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    def allow(self, *, user_id: int | None, group_id: int | None) -> bool:
        if not self.enabled:
            return True

        if user_id is not None and not self._allow(self._user_calls, str(user_id), self.user_max_calls):
            return False

        if group_id is not None and not self._allow(self._group_calls, str(group_id), self.group_max_calls):
            return False

        return True


@dataclass
class Services:
    """外部服务集合（依赖注入）。

这里不强依赖具体类型：只要对象提供对应方法即可。
- deepseek.ask(text) -> str
- vision.ask(image_url) -> str
- image_edit.edit(image_url, prompt) -> str
- memory: MemoryManager (可选)
    """
    deepseek: Any
    vision: Any
    image_edit: Any
    memory: Any = None  # MemoryManager，可选
    rate_limiter: Optional[SimpleRateLimiter] = None
    group_config: Any = None


def _send_msg_payload(
    *,
    user_id: int | None,
    group_id: int | None,
    message_type: str,
    message: str,
) -> dict[str, Any]:
    """构造 OneBot 的 send_msg payload（未编码成 JSON）。"""
    params: dict[str, Any] = {
        "message_type": message_type,
        "message": message,
    }
    if message_type == "group":
        params["group_id"] = group_id
    else:
        params["user_id"] = user_id

    return {"action": "send_msg", "params": params}


@dataclass
class BotContext:
    """单条事件的统一上下文。

用途：
- 命令匹配时，不需要反复从 event 字典里取字段
- 命令执行时，统一用 send_text/send_payload 发消息
    """
    websocket: Any
    event: dict[str, Any]
    settings: BotSettings
    services: Services
    pending_requests: Dict[str, ReplyContext]

    # message-event fields (when post_type == message)
    raw_msg: str = ""
    user_id: int | None = None
    group_id: int | None = None
    message_type: str = "private"
    message_id: int | None = None
    bot_qq: str = ""

    is_message_event: bool = False
    is_reply_callback: bool = False

    is_mentioned: bool = False
    img_url: str | None = None
    reply_id: str | None = None
    text: str = ""

    @classmethod
    def from_event(
        cls,
        *,
        websocket: Any,
        event: dict[str, Any],
        settings: BotSettings,
        services: Services,
        pending_requests: Dict[str, ReplyContext],
    ) -> "BotContext":
        """把原始 event 转成 BotContext，并预计算常用字段。"""
        ctx = cls(
            websocket=websocket,
            event=event,
            settings=settings,
            services=services,
            pending_requests=pending_requests,
        )

        # reply callback
        if (
            event.get("status") == "ok"
            and isinstance(event.get("echo"), str)
            and event.get("echo").startswith("reply_check_")
        ):
            ctx.is_reply_callback = True
            return ctx

        if event.get("post_type") != "message":
            return ctx

        # message event（OneBot 的常规消息）
        ctx.is_message_event = True
        ctx.raw_msg = event.get("raw_message") or ""
        ctx.user_id = event.get("user_id")
        ctx.group_id = event.get("group_id")
        ctx.message_type = event.get("message_type") or "private"
        ctx.message_id = event.get("message_id")
        ctx.bot_qq = str(event.get("self_id"))

        ctx.is_mentioned = contains_at(ctx.raw_msg, ctx.bot_qq)
        ctx.img_url = extract_image_url(ctx.raw_msg)
        ctx.reply_id = extract_reply_id(ctx.raw_msg)
        ctx.text = normalize_user_text(ctx.raw_msg)
        return ctx

    def is_self_message(self) -> bool:
        """过滤机器人自己发出的消息，避免自触发。"""
        return self.event.get("user_id") == self.event.get("self_id")

    def group_behavior(self):
        store = self.services.group_config if self.services else None
        if store is None:
            return None
        return store.get(self.group_id)

    def is_admin(self) -> bool:
        if self.user_id is None:
            return False
        return int(self.user_id) in set(self.settings.admin_user_ids)

    def is_memory_enabled(self) -> bool:
        cfg = self.group_behavior()
        if cfg is None:
            return bool(self.settings.enable_memory)
        return bool(cfg.enable_memory)

    def is_image_enabled(self) -> bool:
        cfg = self.group_behavior()
        if cfg is None:
            return True
        return bool(cfg.enable_image)

    def random_reply_chance(self) -> int:
        cfg = self.group_behavior()
        if cfg is None:
            return max(0, int(self.settings.random_reply_chance))
        return max(0, int(cfg.random_reply_chance))

    async def send_text(self, text: str, *, quote: bool = False) -> None:
        """发送纯文本消息。

quote=True 会自动引用当前 message_id（即回复对方那条消息）。
        """
        if not self.is_message_event:
            return

        if quote and self.message_id is not None:
            msg = f"[CQ:reply,id={self.message_id}] {text}"
        else:
            msg = text

        payload = _send_msg_payload(
            user_id=self.user_id,
            group_id=self.group_id,
            message_type=self.message_type,
            message=msg,
        )
        await self.websocket.send(json.dumps(payload))

    async def send_payload(self, payload: dict[str, Any]) -> None:
        """发送任意 OneBot payload（例如 get_msg / send_msg）。"""
        await self.websocket.send(json.dumps(payload))


class Command(Protocol):
    """可插拔命令协议：match 命中后 run 执行。"""
    name: str

    def match(self, ctx: BotContext) -> bool: ...

    async def run(self, ctx: BotContext) -> bool:
        """返回 True 表示已处理，停止后续匹配。"""


RunFunc = Callable[[BotContext], Awaitable[None]]
MatchFunc = Callable[[BotContext], bool]


@dataclass
class FunctionCommand:
    """把两个函数(match/run) 包装成 Command，方便快速定义命令。"""
    name: str
    _match: MatchFunc
    _run: RunFunc

    def match(self, ctx: BotContext) -> bool:
        return self._match(ctx)

    async def run(self, ctx: BotContext) -> bool:
        await self._run(ctx)
        return True


def keyword_contains(name: str, keyword: str, run: RunFunc, *, require_mentioned: bool = False) -> Command:
    """构造：文本包含 keyword 时触发的命令。"""
    def _match(ctx: BotContext) -> bool:
        if not ctx.is_message_event:
            return False
        if require_mentioned and not ctx.is_mentioned:
            return False
        return keyword in (ctx.text or ctx.raw_msg)

    return FunctionCommand(name=name, _match=_match, _run=run)


def exact_match(name: str, keyword: str, run: RunFunc, *, require_mentioned: bool = False) -> Command:
    """构造：文本完全等于 keyword 时触发的命令。"""
    def _match(ctx: BotContext) -> bool:
        if not ctx.is_message_event:
            return False
        if require_mentioned and not ctx.is_mentioned:
            return False
        return (ctx.text or "").strip() == keyword

    return FunctionCommand(name=name, _match=_match, _run=run)


def prefix(name: str, prefix_text: str, run: RunFunc, *, require_mentioned: bool = False) -> Command:
    """构造：文本以 prefix_text 开头时触发的命令。"""
    def _match(ctx: BotContext) -> bool:
        if not ctx.is_message_event:
            return False
        if require_mentioned and not ctx.is_mentioned:
            return False
        return (ctx.text or "").startswith(prefix_text)

    return FunctionCommand(name=name, _match=_match, _run=run)


def regex(name: str, pattern: str, run: RunFunc, *, require_mentioned: bool = False) -> Command:
    """构造：正则命中时触发的命令。"""
    compiled = re.compile(pattern)

    def _match(ctx: BotContext) -> bool:
        if not ctx.is_message_event:
            return False
        if require_mentioned and not ctx.is_mentioned:
            return False
        return compiled.search(ctx.text or ctx.raw_msg) is not None

    return FunctionCommand(name=name, _match=_match, _run=run)


def cleanup_expired_pending_requests(pending_requests: Dict[str, ReplyContext], ttl_seconds: float = 60.0) -> None:
    """清理超时的 reply 回调上下文。"""
    now = time.time()
    expired = [
        key
        for key, value in pending_requests.items()
        if value.created_at and now - value.created_at > ttl_seconds
    ]
    for key in expired:
        pending_requests.pop(key, None)
    if expired:
        logger.debug("cleaned expired pending requests: count=%s", len(expired))




async def dispatch(commands: Iterable[Command], ctx: BotContext) -> bool:
    """按顺序匹配命令并执行；有命令返回 True 即停止。"""
    cleanup_expired_pending_requests(ctx.pending_requests)

    if ctx.is_message_event and ctx.services.rate_limiter:
        allowed = ctx.services.rate_limiter.allow(user_id=ctx.user_id, group_id=ctx.group_id)
        if not allowed:
            await ctx.send_text("消息有点多啦，稍等一下再试试吧~", quote=True)
            logger.info("rate-limited: user=%s group=%s", ctx.user_id, ctx.group_id)
            return True

    for cmd in commands:
        if cmd.match(ctx):
            handled = await cmd.run(ctx)
            if handled:
                return True
    return False


# --------- 一些内置“通用命令”实现（后面在 commands.py 里组装顺序） ---------

async def run_reply_callback(ctx: BotContext) -> None:
    """处理回复消息的回调（集成记忆模块）。"""
    echo_id = ctx.event.get("echo")
    saved = ctx.pending_requests.pop(echo_id, None)
    if not saved:
        return

    logger.info("收到 get_msg 响应: %s", echo_id)
    msg_data = ctx.event.get("data", {})
    target_msg = msg_data.get("raw_message") or str(msg_data.get("message", ""))
    user_id = str(saved.user_id) if saved.user_id else None

    target_img_url = extract_image_url(target_msg)
    user_msg_clean = normalize_user_text(saved.raw_msg)

    if target_img_url:
        if not ctx.is_image_enabled():
            reply_text = "本群已关闭图片能力~"
        else:
            logger.info("在被回复的消息中找到了图片")

            if user_msg_clean.startswith("编辑="):
                edit_prompt = user_msg_clean[3:].strip()
                if not edit_prompt:
                    reply_text = "请在'编辑='后面加上你的修图指令哦~"
                else:
                    reply_text = await ctx.services.image_edit.edit(target_img_url, edit_prompt)
            else:
                reply_text = await ctx.services.vision.ask(target_img_url)
    else:
        logger.info("被回复消息无图片，转为文本回复")
        user_question = user_msg_clean or "（盯着你回复的消息看）"
        full_prompt = f"我回复了消息：'{target_msg}'。\n我的评论是：{user_question}"
        reply_text = await ctx.services.deepseek.ask(full_prompt)

    # 记录到 STM（如果有记忆模块）
    if ctx.services.memory and user_id and ctx.is_memory_enabled():
        try:
            memory = ctx.services.memory
            trigger_type = "reply_with_image" if target_img_url else "reply_text"

            # 识别用户情绪（用用户本次回复文本；为空则用兜底短句）
            try:
                emotion_text = user_msg_clean or "（回复了一条消息）"
                user_emotion = await memory.emotion_recognizer.recognize_async(emotion_text)
            except Exception as emo_err:
                logger.warning("回复场景情绪识别失败: %s", emo_err)
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
                logger.debug("bot_emotion tone=%s V=%.2f A=%.2f D=%.2f", bot_state.get_suggested_tone(), bot_state.V, bot_state.A, bot_state.D)
            logger.info("%s user=%s reply_len=%s", trigger_type, user_id, len(reply_text))
        except Exception as e:
            logger.warning("回复场景记忆写入失败: %s", e)

    payload = _send_msg_payload(
        user_id=saved.user_id,
        group_id=saved.group_id,
        message_type=saved.message_type,
        message=f"[CQ:reply,id={saved.message_id}] {reply_text}",
    )
    await ctx.send_payload(payload)

async def run_mentioned_with_image(ctx: BotContext) -> None:
    """处理 @机器人 + 图片（集成记忆模块）。"""
    if not ctx.is_image_enabled():
        await ctx.send_text("本群已关闭图片能力~", quote=True)
        return

    user_id = str(ctx.user_id) if ctx.user_id else None
    img_description = ctx.text or "看看这张图"
    
    # 调用视觉模型
    reply_text = await ctx.services.vision.ask(ctx.img_url or "")
    
    # 记录到 STM（如果有记忆模块）
    if ctx.services.memory and user_id and ctx.is_memory_enabled():
        try:
            memory = ctx.services.memory

            # 识别用户情绪（用用户随图附带的文字/描述）
            try:
                user_emotion = await memory.emotion_recognizer.recognize_async(img_description)
            except Exception as emo_err:
                logger.warning("图片场景情绪识别失败: %s", emo_err)
                user_emotion = None
            
            # 记录用户发图行为
            await memory.append_to_stm(
                user_id=user_id,
                role="user",
                text=f"[发送图片] {img_description}",
                meta={
                    "trigger": "mentioned_with_image",
                    "has_image": True,
                    "emotion": getattr(user_emotion, "label", None),
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
            if user_emotion is not None:
                bot_state = await memory.update_bot_emotion(user_emotion, user_id)
                logger.debug("bot_emotion tone=%s V=%.2f A=%.2f D=%.2f", bot_state.get_suggested_tone(), bot_state.V, bot_state.A, bot_state.D)
            logger.info("mentioned_with_image user=%s reply_len=%s", user_id, len(reply_text))
        except Exception as e:
            logger.warning("图片场景记忆写入失败: %s", e)
    
    await ctx.send_text(reply_text, quote=True)


async def run_mentioned_with_reply(ctx: BotContext) -> None:
    # 发送 get_msg 请求，并把当前上下文塞进 pending，等待回调
    if ctx.message_id is None or not ctx.reply_id:
        return

    logger.info("检测到回复消息，正在获取原消息内容: id=%s", ctx.reply_id)
    echo_id = f"reply_check_{ctx.message_id}"
    ctx.pending_requests[echo_id] = ReplyContext(
        user_id=ctx.user_id,
        group_id=ctx.group_id,
        message_type=ctx.message_type,
        message_id=ctx.message_id,
        raw_msg=ctx.raw_msg,
        created_at=time.time(),
    )
    req = {"action": "get_msg", "params": {"message_id": ctx.reply_id}, "echo": echo_id}
    await ctx.send_payload(req)


async def run_mentioned_text(ctx: BotContext) -> None:
    """处理 @机器人 的纯文本消息（集成记忆模块）。"""
    question = ctx.text or "你叫我干嘛？"
    user_id = str(ctx.user_id) if ctx.user_id else None

    # 如果有记忆模块，使用增强对话
    if ctx.services.memory and user_id and ctx.is_memory_enabled():
        try:
            memory = ctx.services.memory

            # 0) 识别用户情绪（优先 LLM，失败自动降级）
            user_emotion = await memory.emotion_recognizer.recognize_async(question)

            # 1) 记录“用户本轮输入”到 STM（仅自然语言对话才写入）
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
            logger.debug("bot_emotion tone=%s V=%.2f A=%.2f D=%.2f", bot_state.get_suggested_tone(), bot_state.V, bot_state.A, bot_state.D)

            if user_emotion.label in ("angry", "disgust") and user_emotion.intensity > 0.6:
                await memory.update_relation_on_negative_emotion(user_id, user_emotion.intensity)

            # 8. 异步任务：LTM提取和人格分析（不阻塞回复）
            async def _post_reply_tasks() -> None:
                try:
                    await memory.extract_ltm_from_stm(user_id)
                    await memory.maybe_update_personality(user_id, ctx.services.deepseek)
                except Exception as bg_err:
                    logger.warning("后台任务失败: %s", bg_err)

            asyncio.create_task(_post_reply_tasks())
            logger.info("mentioned_text user=%s emo=%s reply_len=%s", user_id, user_emotion.label, len(reply_text))

        except Exception as e:
            logger.warning("记忆模块对话失败，降级到普通模式: %s", e)
            reply_text = await ctx.services.deepseek.ask(question)
    else:
        # 无记忆模块，使用普通模式
        reply_text = await ctx.services.deepseek.ask(question)

    await ctx.send_text(reply_text, quote=False)


async def run_random_chitchat(ctx: BotContext) -> None:
    """随机触发闲聊（集成记忆模块）。"""
    chance = ctx.random_reply_chance()
    if chance <= 0:
        return
    if random.randint(1, chance) != 1:
        return
    
    logger.info("随机触发闲聊")
    user_id = str(ctx.user_id) if ctx.user_id else None
    question = ctx.raw_msg

    # 如果有记忆模块，使用增强对话
    if ctx.services.memory and user_id and ctx.is_memory_enabled():
        try:
            memory = ctx.services.memory

            # 0) 识别用户情绪（优先 LLM，失败自动降级）
            user_emotion = await memory.emotion_recognizer.recognize_async(question)

            # 1) 只有触发了闲聊回复，才把用户输入写入 STM
            await memory.append_to_stm(
                user_id=user_id,
                role="user",
                text=question,
                meta={
                    "message_type": ctx.message_type,
                    "group_id": ctx.group_id,
                    "trigger": "random_chitchat",
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

            # 4. 获取历史对话（随机闲聊用更少的历史）
            stm = memory.get_stm(user_id)
            messages = build_chat_messages(
                stm=stm,
                current_question=question,
                system_prompt=system_prompt,
                max_history=6,
            )

            # 5. 调用 LLM（多轮）
            reply_text = await ctx.services.deepseek.ask_with_messages(messages)

            # 6. 记录机器人回复到 STM
            await memory.append_to_stm(
                user_id=user_id,
                role="assistant",
                text=reply_text,
                meta={"trigger": "random_chitchat"},
            )

            # 7. 更新关系
            await memory.update_relation_on_interaction(user_id)

            # 8. 更新并打印机器人情绪
            bot_state = await memory.update_bot_emotion(user_emotion, user_id)
            logger.debug("bot_emotion tone=%s V=%.2f A=%.2f D=%.2f", bot_state.get_suggested_tone(), bot_state.V, bot_state.A, bot_state.D)

            if user_emotion.label in ("angry", "disgust") and user_emotion.intensity > 0.6:
                await memory.update_relation_on_negative_emotion(user_id, user_emotion.intensity)

            logger.info("random_chitchat user=%s emo=%s reply_len=%s", user_id, user_emotion.label, len(reply_text))

        except Exception as e:
            logger.warning("记忆模块闲聊失败，降级到普通模式: %s", e)
            reply_text = await ctx.services.deepseek.ask(question)
    else:
        # 无记忆模块，使用普通模式
        reply_text = await ctx.services.deepseek.ask(question)

    await ctx.send_text(reply_text, quote=False)
