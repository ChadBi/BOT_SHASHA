"""Bing 壁纸抓取+下载的小工具脚本（与机器人核心无关）。

用途：
- 拉取 Bing daily JSON
- 取第一张图片的 url + hsh
- 下载到 BOT/shasha_bot/pic/ 下，并用 hsh 命名避免重复
"""

import http.client
import json
import httpx
import os

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
print(json.dumps(test, ensure_ascii=False, indent=2))
# print(data.decode("utf-8"))

path = test["url"]
host = "https://www.bing.com"
# 3) 拼接完整下载链接
url = f"{host}{path}"
hsh = test["hsh"]

filename = f"{hsh}.jpg"

# 4) 保存路径（相对仓库根目录）
sava_path = f"BOT\\shasha_bot\\pic\\{filename}"

if os.path.exists(sava_path):
    print("文件已存在，跳过下载")
else:
    # 5) 下载图片
    response = httpx.get(url)
    print(response)
    with open(sava_path, "wb") as f:
        f.write(response.content)