"""遗留脚本（v0.1）。

说明：
- 这个文件是早期单文件版本，保留做参考。
- 现在推荐使用模块化版本：BOT/run_bot.py + BOT/shasha_bot/*。
- 新增功能请优先写在 shasha_bot/commands_custom.py。
"""

import asyncio
import json
import websockets
import random
import base64
import httpx
import re  # 引入正则库，用来提取图片链接
import os
from zai import ZhipuAiClient
from openai import AsyncOpenAI

# ================= 配置区域 =================
# 1. 你的 DeepSeek Key (负责聊天)
DEEPSEEK_API_KEY = "sk-23b6d0f106f948369e32dec38e2a8a1c" 
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# 2. 你的 视觉模型 Key (负责看图，推荐阿里云 DashScope)
ZHIPU_API_KEY = "5d4df470843d473c91cd39b86a7e891e.7aLU3PH4OjQECx4T" 
VISION_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"

# 概率配置
RANDOM_REPLY_CHANCE = 200

# 初始化 DeepSeek 客户端（文本）
text_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# 初始化智谱客户端（官方 SDK 推荐方式）
zhipu_client = ZhipuAiClient(api_key=ZHIPU_API_KEY)

SYSTEM_PROMPT = "你是一个傲娇的二次元美少女机器人，说话要带一点颜文字，名字叫'鲨鲨'。"
VISION_PROMPT = "你是一个比较专业的摄影师，请简短评价下面的图片内容，不要超过100个字。评价可以稍微抽象幽默一点，偶尔也可以批评讽刺，但不要太过分。"
# ===========================================

# --- 功能函数：从消息中提取图片 URL ---
def get_image_url(msg):
    # QQ 的图片消息格式通常是 [CQ:image,file=xxx,url=http://xxx]
    # 我们用正则表达式提取 url= 后面的地址
    match = re.search(r'\[CQ:image,.*?url=(http[^,\]]+)', msg)
    print(f"提取到的图片链接: {match.group(1) if match else '无'}")
    if match:
        return match.group(1)
    return None

async def encode_image_to_base64(image_url):
    try:
        async with httpx.AsyncClient() as client:
            # 你的机器人本地去下载图片，通常没问题
            resp = await client.get(image_url, timeout=10.0)
            if resp.status_code == 200:
                # 转为 Base64
                base64_data = base64.b64encode(resp.content).decode('utf-8')
                # 智谱要求的格式通常不需要前缀，但在 SDK 中还是建议带上 mime type，或者直接给纯 base64
                # OpenAI 格式通常支持 data uri: f"data:image/jpeg;base64,{base64_data}"
                return f"data:image/jpeg;base64,{base64_data}"
    except Exception as e:
        print(f"图片转码失败: {e}")
    return None

# --- AI 函数 1: 纯文本聊天 (DeepSeek) ---
async def ask_deepseek(question: str) -> str:
    if not DEEPSEEK_API_KEY:
        return "未配置 DEEPSEEK_API_KEY"
    try:
        response = await text_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            stream=False,
            temperature=1.3,
            max_tokens=100,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ 文本 AI 出错: {e}")
        return "脑子瓦特了..."

# --- AI 函数 2: 看图说话 ---
async def ask_vision_ai(image_input):
    try:
        #print(f"👀 正在查看图片: {image_input}")
        if not ZHIPU_API_KEY:
            return "未配置 ZHIPU_API_KEY"

        def _call():
            print("📌 开始调用智谱AI接口")
            res =zhipu_client.chat.completions.create(
                model="glm-4.6v",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{SYSTEM_PROMPT},{VISION_PROMPT} 请评价一下这张图片，简短一点，不要超过100个字。"},
                            {"type": "image_url", "image_url": {"url": image_input}},
                        ],
                    }
                ],
                temperature=1.3,
            )
            print(f"📌 接口调用完成，返回对象：{res}")
            return res

        response = await asyncio.to_thread(_call)
        #print(f"👀 图片分析完成: {response.choices[0].message.content}")
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ 视觉 AI 出错: {e}")
        return "图片加载失败了捏..."


# --- 主逻辑 ---
async def handle_message(websocket):
    print("✅ 连接成功！")
    try:
        async for message in websocket:
            event = json.loads(message)
            # print(event) # 调试时可以取消这行注释，看看原始数据

            if event.get('post_type') == 'message':
                raw_msg = event.get('raw_message')
                user_id = event.get('user_id')
                message_type = event.get('message_type')
                group_id = event.get('group_id')
                message_id = event.get('message_id') # 方便引用回复

                # 过滤掉自己发的消息
                if event.get('user_id') == event.get('self_id'):
                    continue

                print(f"📩 [{user_id}][{message_type}] 收到: {raw_msg}")

                # ================= 核心逻辑判断 =================
                
                # --- 1. 获取机器人的 QQ 号和 @ 他的 CQ 码 ---
                bot_qq = str(event.get('self_id'))
                at_me_code = f"[CQ:at,qq={bot_qq}]"
                
                # --- 2. 检查是否被 @ ---
                is_mentioned = at_me_code in raw_msg
                
                # --- 3. 提取图片链接 ---
                img_url = get_image_url(raw_msg)
                clean_url = re.sub(r'&amp;', '&', img_url) if img_url else None
                
                # --- 4. 判断：是否被 @ 并且包含图片？ ---
                if is_mentioned and img_url:
                    print("🕵️ 被艾特了，并且收到了图片！切换视觉模式...")
                    
                    # 清洗消息，去掉 @ 代码，方便 AI 理解
                    question_content = raw_msg.replace(at_me_code, "").strip()
                    if not question_content: # 如果只 @ 了没说话，默认提问
                        question_content = "评价一下这张图"

                    # 调用视觉 AI
                    reply_text = await ask_vision_ai(clean_url)
                    print(f"💡 视觉 AI 回复: {reply_text}")
                    
                    # 构造回复 (引用回复 + AI 评价)
                    reply_data = {
                        "action": "send_msg",
                        "params": {
                            "user_id": user_id,
                            "group_id": group_id,
                            "message_type": message_type,
                            "message": f"[CQ:reply,id={message_id}] {reply_text}" 
                        }
                    }
                    await websocket.send(json.dumps(reply_data))
                    continue # 图片处理完，本次消息就不往下走其他逻辑了

                # --- 5. 如果只是被 @ 但没有图片 ---
                elif is_mentioned:
                    print("📢 被艾特了，但没有图片，切换纯文本模式...")
                    # 清洗消息，去掉 @ 代码
                    question = raw_msg.replace(at_me_code, "").strip()
                    if not question:
                        question = "你叫我干嘛？"
                    reply_text = await ask_deepseek(question)
                    
                    reply_data = {
                        "action": "send_msg",
                        "params": {
                            "user_id": user_id,
                            "group_id": group_id,
                            "message_type": message_type,
                            "message": reply_text
                        }
                    }
                    await websocket.send(json.dumps(reply_data))
                    continue # 处理完 @ 消息，本次消息也不往下走

                # --- 6. 如果不是 @ 且没有图片 (保持原来的随机闲聊逻辑) ---
                else:
                    choice = random.randint(1, RANDOM_REPLY_CHANCE)
                    if choice == 1:
                        print("🤖 随机触发闲聊...")
                        reply_text = await ask_deepseek(raw_msg)
                        
                        reply_data = {
                            "action": "send_msg",
                            "params": {
                                "user_id": user_id,
                                "group_id": group_id,
                                "message_type": message_type,
                                "message": reply_text
                            }
                        }
                        await websocket.send(json.dumps(reply_data))

    except websockets.exceptions.ConnectionClosed:
        print("⚠️ 连接断开")

# --- main 函数保持不变 ---
async def main():
    print("🤖 鲨鲨启动中 (端口 8080)...")
    async with websockets.serve(handle_message, "0.0.0.0", 8080) as server:
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())