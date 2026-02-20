from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

import httpx

from .router import Command, exact_match, prefix, regex
from .memory import MemoryManager, format_memory_summary

BING_JSON_URL = "https://raw.onmicrosoft.cn/Bing-Wallpaper-Action/main/data/zh-CN_update.json"
BING_HOST = "https://www.bing.com"
CACHE_DIR = Path("shasha_bot/pic")


def get_memory_manager(ctx) -> Optional[MemoryManager]:
    """从 context 中获取记忆管理器。"""
    if not ctx.is_memory_enabled():
        return None
    if ctx.services and ctx.services.memory:
        return ctx.services.memory
    return None

VISION_PROMPT = (
    "你是专业的影像摄影师，请详细介绍这张必应每日壁纸的拍摄亮点和美学价值，以及相关的摄影技巧。\n"
    "请控制在200字以内。不要使用markdown格式。一两段话就说完"
)

MENU_TEXT = """🤖 菜单

【常用】
1、每日一图
2、正常聊天（@我 + 文字）

【图片】
1、图片编辑（@我 回复图片 + 编辑=需求）
2、图片评论（@我 发送或回复图片 + 文字）

【记忆】（需要@我）
1、昵称=xxx（设置你的昵称）
2、自述=xxx（告诉我关于你的信息）
3、查看记忆（查看我记住的信息）
4、清除自述（清除你的自述）
5、清除记忆（清除短期记忆和自述）

【管理员】
1、设置随机率=数字（0 表示关闭随机闲聊）
2、开关记忆=开/关
3、查看运行状态
"""


async def _fetch_bing_today() -> tuple[str, str]:
    """返回 (image_url, hsh)"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(BING_JSON_URL)
        resp.raise_for_status()
        data = resp.json()

    img = data["images"][0]
    url = f"{BING_HOST}{img['url']}"
    hsh = img["hsh"]
    return url, hsh


def _cache_path(hsh: str) -> Path:
    return CACHE_DIR / f"{hsh}.txt"


def _read_cache(hsh: str) -> Optional[str]:
    p = _cache_path(hsh)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def _write_cache(hsh: str, text: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(hsh).write_text(text, encoding="utf-8")


async def _daily_img(ctx):
    url, hsh = await _fetch_bing_today()

    # 先发图
    await ctx.send_text(f"[CQ:image,url={url}]", quote=False)

    # 读缓存
    cached = _read_cache(hsh)
    if cached:
        await asyncio.sleep(1)
        await ctx.send_text(cached, quote=False)
        return

    # 调 vision 并缓存
    text = await ctx.services.vision.ask(url, prompt=VISION_PROMPT)
    _write_cache(hsh, text)
    await ctx.send_text(text, quote=False)


async def _menu(ctx):
    await ctx.send_text(MENU_TEXT, quote=False)


# ================== 记忆相关命令 ==================

async def _set_nickname(ctx):
    """设置昵称命令：昵称=xxx"""
    text = ctx.text or ""
    if not text.startswith("昵称="):
        return
    nickname = text[3:].strip()
    if not nickname:
        await ctx.send_text("昵称不能为空哦~", quote=True)
        return
    if len(nickname) > 20:
        await ctx.send_text("昵称太长啦，最多20个字~", quote=True)
        return

    manager = get_memory_manager(ctx)
    if not manager:
        await ctx.send_text("记忆功能未启用~", quote=True)
        return

    user_id = str(ctx.user_id)
    await manager.set_nickname(user_id, nickname)
    await ctx.send_text(f"好的，以后就叫你「{nickname}」啦~ ✧", quote=True)


async def _add_self_desc(ctx):
    """添加自述命令：自述=xxx"""
    text = ctx.text or ""
    if not text.startswith("自述="):
        return
    desc = text[3:].strip()
    if not desc:
        await ctx.send_text("自述内容不能为空哦~", quote=True)
        return
    if len(desc) > 200:
        await ctx.send_text("自述太长啦，最多200个字~", quote=True)
        return

    manager = get_memory_manager(ctx)
    if not manager:
        await ctx.send_text("记忆功能未启用~", quote=True)
        return

    user_id = str(ctx.user_id)
    await manager.add_self_description(user_id, desc)
    await ctx.send_text("已记住你的介绍啦~ (≧▽≦)/", quote=True)


async def _view_memory(ctx):
    """查看记忆命令"""
    manager = get_memory_manager(ctx)
    if not manager:
        await ctx.send_text("记忆功能未启用~", quote=True)
        return

    user_id = str(ctx.user_id)
    summary = await manager.get_user_summary(user_id)
    text = format_memory_summary(summary)
    await ctx.send_text(text, quote=True)


async def _clear_self_desc(ctx):
    """清除自述命令"""
    manager = get_memory_manager(ctx)
    if not manager:
        await ctx.send_text("记忆功能未启用~", quote=True)
        return

    user_id = str(ctx.user_id)
    await manager.clear_self_descriptions(user_id)
    await ctx.send_text("已清除你的所有自述~ ", quote=True)


async def _clear_memory(ctx):
    """清除记忆命令（清除短期记忆和自述）"""
    manager = get_memory_manager(ctx)
    if not manager:
        await ctx.send_text("记忆功能未启用~", quote=True)
        return

    user_id = str(ctx.user_id)
    await manager.clear_stm(user_id)
    await manager.clear_self_descriptions(user_id)
    await ctx.send_text("已清除我对你的短期记忆和自述~", quote=True)


async def _view_bot_emotion(ctx):
    """查看机器人当前情感状态（VAD）。"""
    manager = get_memory_manager(ctx)
    if not manager:
        await ctx.send_text("记忆功能未启用，当前没有情感状态可查看~", quote=True)
        return

    state = manager.get_bot_emotion()
    await ctx.send_text(
        f"我现在的状态：{state.get_suggested_tone()} | V={state.V:.2f} A={state.A:.2f} D={state.D:.2f}",
        quote=True,
    )




def _is_group_message(ctx) -> bool:
    return ctx.message_type == "group" and ctx.group_id is not None


async def _ensure_admin(ctx) -> bool:
    if ctx.is_admin():
        return True
    await ctx.send_text("该命令仅管理员可用~", quote=True)
    return False


async def _set_random_rate(ctx):
    if not _is_group_message(ctx):
        await ctx.send_text("请在群聊中使用该命令~", quote=True)
        return
    if not await _ensure_admin(ctx):
        return

    text = (ctx.text or "").strip()
    raw = text.split("=", 1)[1].strip() if "=" in text else ""
    try:
        value = int(raw)
    except Exception:
        await ctx.send_text("随机率格式不对，请使用：设置随机率=数字", quote=True)
        return

    if value < 0:
        await ctx.send_text("随机率不能小于 0 哦~", quote=True)
        return

    updated = ctx.services.group_config.update_random_reply_chance(ctx.group_id, value)
    await ctx.send_text(f"已更新本群随机率为 {updated.random_reply_chance}。", quote=True)


async def _switch_memory(ctx):
    if not _is_group_message(ctx):
        await ctx.send_text("请在群聊中使用该命令~", quote=True)
        return
    if not await _ensure_admin(ctx):
        return

    text = (ctx.text or "").strip()
    value = text.split("=", 1)[1].strip() if "=" in text else ""
    if value not in {"开", "关"}:
        await ctx.send_text("格式应为：开关记忆=开 或 开关记忆=关", quote=True)
        return

    enabled = value == "开"
    updated = ctx.services.group_config.update_enable_memory(ctx.group_id, enabled)
    await ctx.send_text(f"本群记忆功能已{'开启' if updated.enable_memory else '关闭'}。", quote=True)


async def _view_runtime_status(ctx):
    if not _is_group_message(ctx):
        await ctx.send_text("请在群聊中使用该命令~", quote=True)
        return
    if not await _ensure_admin(ctx):
        return

    cfg = ctx.group_behavior()
    if cfg is None:
        await ctx.send_text("未加载群配置。", quote=True)
        return

    await ctx.send_text(
        "\n".join(
            [
                "📊 本群运行状态",
                f"- 随机闲聊随机率: {cfg.random_reply_chance}",
                f"- 记忆功能: {'开' if cfg.enable_memory else '关'}",
                f"- 图片功能: {'开' if cfg.enable_image else '关'}",
                f"- 全局记忆模块: {'已加载' if ctx.services.memory else '未加载'}",
            ]
        ),
        quote=True,
    )


CUSTOM_COMMANDS: List[Command] = [
    exact_match("daily_img", "每日一图", _daily_img, require_mentioned=False),
    exact_match("menu", "菜单", _menu, require_mentioned=False),
    regex("admin_set_random_rate", r"^设置随机率\s*=", _set_random_rate, require_mentioned=False),
    regex("admin_switch_memory", r"^开关记忆\s*=", _switch_memory, require_mentioned=False),
    exact_match("admin_view_runtime_status", "查看运行状态", _view_runtime_status, require_mentioned=False),
    # 记忆相关命令（需要 @）
    prefix("set_nickname", "昵称=", _set_nickname, require_mentioned=True),
    prefix("add_self_desc", "自述=", _add_self_desc, require_mentioned=True),
    exact_match("view_memory", "查看记忆", _view_memory, require_mentioned=True),
    exact_match("view_bot_emotion", "查看情感", _view_bot_emotion, require_mentioned=True),
    exact_match("clear_self_desc", "清除自述", _clear_self_desc, require_mentioned=True),
    exact_match("clear_memory", "清除记忆", _clear_memory, require_mentioned=True),
]
