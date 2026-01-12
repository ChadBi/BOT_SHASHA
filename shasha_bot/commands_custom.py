"""你以后新增功能，主要改这个文件就行。

思路：添加一个 Command 到 CUSTOM_COMMANDS 列表。

例 1：提到关键词就回复

from .router import keyword_contains

async def _ping(ctx):
    await ctx.send_text("pong", quote=True)

CUSTOM_COMMANDS = [
    keyword_contains("ping", "ping", _ping, require_mentioned=True),
]

例 2：前缀命令（比如：搜=xxx）

from .router import prefix

async def _echo(ctx):
    await ctx.send_text(f"你说的是：{ctx.text}", quote=True)

CUSTOM_COMMANDS = [
    prefix("echo", "echo=", _echo, require_mentioned=True),
]

说明：
- require_mentioned=True 表示必须 @ 机器人时才触发，避免群里误触。
- 如果你想“无论是否 @ 都触发”，把 require_mentioned=False。
"""

from __future__ import annotations
import json
import os
from time import sleep
import httpx
from typing import List
import http.client
from .router import Command,exact_match
from .ai.zhipu_vision import ZhipuVision
async def _daily_img(ctx):
    conn = http.client.HTTPSConnection("raw.onmicrosoft.cn")
    payload = ''
    headers = {}
    # 1) 获取 JSON
    conn.request("GET", "/Bing-Wallpaper-Action/main/data/zh-CN_update.json", payload, headers)
    res = conn.getresponse()
    data = res.read()
    data = json.loads(data.decode("utf-8"))
    # 2) 取第一张图
    test = data["images"][0]
    path = test["url"]
    host = "https://www.bing.com"
    # 3) 拼接完整下载链接
    url = f"{host}{path}"
    hsh = test["hsh"]
    filename = f"{hsh}"
    # print(json.dumps(test, ensure_ascii=False, indent=2))
    await ctx.send_text(f"[CQ:image,url={url}]", quote=False)
    if os.path.exists(f"shasha_bot/pic/{filename}.txt"):
        print("文件已存在，跳过下载")
        with open(f"shasha_bot/pic/{filename}.txt", "r", encoding="utf-8") as f:
            respond = f.read()
        sleep(1)
        await ctx.send_text(respond, quote=False)
    else:
        respond = await ctx.services.vision.ask(url, prompt="你是专业的影像摄影师，请详细介绍这张必应每日壁纸的拍摄亮点和美学价值，以及相关的摄影技巧。\n请控制在200字以内。不要使用markdown格式。一两段话就说完")
        with open(f"shasha_bot/pic/{filename}.txt", "w", encoding="utf-8") as f:
            f.write(respond)
        await ctx.send_text(respond, quote=False)

CUSTOM_COMMANDS: List[Command] = [exact_match("daily_img", "每日一图", _daily_img, require_mentioned=False)]

