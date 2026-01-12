"""CQ 码解析/清洗。

OneBot/NapCat 发来的消息包含类似：
- [CQ:at,qq=123]
- [CQ:reply,id=456]
- [CQ:image,...,url=http...]

本模块把这些 CQ 码提取/去掉，方便后续命令匹配与 AI 调用。
"""

from __future__ import annotations

import re
from typing import Optional


# 提取图片的 url=...（只抓 http 开头的那段）
_CQ_IMAGE_URL_RE = re.compile(r"\[CQ:image,.*?url=(http[^,\]]+)")
# 匹配 @ 机器人/用户
_CQ_AT_RE = re.compile(r"\[CQ:at,qq=(\d+)\]")
# 匹配“回复某条消息”的 id
_CQ_REPLY_RE = re.compile(r"\[CQ:reply,id=(\d+)\]")


def extract_image_url(message: str) -> Optional[str]:
    """从 CQ:image 中提取 url=... 并做基础清洗（&amp; -> &）。"""
    match = _CQ_IMAGE_URL_RE.search(message or "")
    if not match:
        return None
    url = match.group(1)
    # CQ 里常见 &amp;
    url = url.replace("&amp;", "&")
    return url


def extract_reply_id(message: str) -> Optional[str]:
    """提取 CQ:reply 的 message_id。"""
    match = _CQ_REPLY_RE.search(message or "")
    return match.group(1) if match else None


def contains_at(message: str, qq: str) -> bool:
    """判断消息是否包含 @ 指定 QQ 的 CQ 码。"""
    if not message:
        return False
    return f"[CQ:at,qq={qq}]" in message


def strip_at(message: str) -> str:
    """移除所有 CQ:at。"""
    return _CQ_AT_RE.sub("", message or "")


def strip_reply(message: str) -> str:
    """移除所有 CQ:reply。"""
    return _CQ_REPLY_RE.sub("", message or "")


def normalize_user_text(message: str) -> str:
    """清洗掉 @ 和 reply 等 CQ 码，得到用户真实输入。"""
    cleaned = strip_reply(strip_at(message))
    return cleaned.strip()
