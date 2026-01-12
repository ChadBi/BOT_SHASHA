"""命令路由与上下文（扩展功能的核心）。

这套机制的目标：
- 把“很多 if/elif”变成“按优先级排列的命令列表”
- 以后新增功能：只需要添加一个 Command（见 commands_custom.py）

关键概念：
- BotContext：一条事件的“上下文”，包含解析后的字段、AI 服务、发送消息方法
- Command：匹配(match) + 执行(run) 的可插拔单元
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional, Protocol

from .cq import extract_image_url, extract_reply_id, contains_at, normalize_user_text
from .settings import BotSettings


@dataclass
class ReplyContext:
    """用于异步回调场景：保存 `get_msg` 请求发出时的上下文。"""
    user_id: int | None
    group_id: int | None
    message_type: str
    message_id: int
    raw_msg: str


@dataclass
class Services:
    """外部服务集合（依赖注入）。

这里不强依赖具体类型：只要对象提供对应方法即可。
- deepseek.ask(text) -> str
- vision.ask(image_url) -> str
- image_edit.edit(image_url, prompt) -> str
    """
    deepseek: Any
    vision: Any
    image_edit: Any


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


async def dispatch(commands: Iterable[Command], ctx: BotContext) -> bool:
    """按顺序匹配命令并执行；有命令返回 True 即停止。"""
    for cmd in commands:
        if cmd.match(ctx):
            handled = await cmd.run(ctx)
            if handled:
                return True
    return False


# --------- 一些内置“通用命令”实现（后面在 commands.py 里组装顺序） ---------

async def run_reply_callback(ctx: BotContext) -> None:
    echo_id = ctx.event.get("echo")
    saved = ctx.pending_requests.pop(echo_id, None)
    if not saved:
        return

    print(f"🔄 收到 get_msg 响应: {echo_id}")
    msg_data = ctx.event.get("data", {})
    target_msg = msg_data.get("raw_message") or str(msg_data.get("message", ""))

    target_img_url = extract_image_url(target_msg)

    if target_img_url:
        print("🕵️ 在被回复的消息中找到了图片！")
        user_msg_clean = normalize_user_text(saved.raw_msg)

        if user_msg_clean.startswith("编辑="):
            edit_prompt = user_msg_clean[3:].strip()
            if not edit_prompt:
                reply_text = "请在'编辑='后面加上你的修图指令哦~"
            else:
                reply_text = await ctx.services.image_edit.edit(target_img_url, edit_prompt)
        else:
            reply_text = await ctx.services.vision.ask(target_img_url)

        payload = _send_msg_payload(
            user_id=saved.user_id,
            group_id=saved.group_id,
            message_type=saved.message_type,
            message=f"[CQ:reply,id={saved.message_id}] {reply_text}",
        )
        await ctx.send_payload(payload)
        return

    print("⚠️ 被回复的消息里没有图片，转为普通文本回复...")
    user_question = normalize_user_text(saved.raw_msg) or "（盯着你回复的消息看）"
    full_prompt = f"我回复了消息：“{target_msg}”。\n我的评论是：{user_question}"
    reply_text = await ctx.services.deepseek.ask(full_prompt)

    payload = _send_msg_payload(
        user_id=saved.user_id,
        group_id=saved.group_id,
        message_type=saved.message_type,
        message=f"[CQ:reply,id={saved.message_id}] {reply_text}",
    )
    await ctx.send_payload(payload)


async def run_mentioned_with_image(ctx: BotContext) -> None:
    reply_text = await ctx.services.vision.ask(ctx.img_url or "")
    await ctx.send_text(reply_text, quote=True)


async def run_mentioned_with_reply(ctx: BotContext) -> None:
    # 发送 get_msg 请求，并把当前上下文塞进 pending，等待回调
    if ctx.message_id is None or not ctx.reply_id:
        return

    print(f"🔗 检测到回复消息，正在获取原消息内容 (ID: {ctx.reply_id})...")
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


async def run_mentioned_text(ctx: BotContext) -> None:
    question = ctx.text or "你叫我干嘛？"
    reply_text = await ctx.services.deepseek.ask(question)
    await ctx.send_text(reply_text, quote=False)


async def run_random_chitchat(ctx: BotContext) -> None:
    chance = max(1, ctx.settings.random_reply_chance)
    if random.randint(1, chance) != 1:
        return
    print("🤖 随机触发闲聊...")
    reply_text = await ctx.services.deepseek.ask(ctx.raw_msg)
    await ctx.send_text(reply_text, quote=False)
