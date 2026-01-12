"""智谱视觉模型封装。

说明：zai 的 SDK 调用是同步的，这里用 asyncio.to_thread 放到线程池里，
避免阻塞主事件循环。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from zai import ZhipuAiClient


@dataclass
class ZhipuVision:
    """图片评价/描述（视觉模型）。"""
    api_key: str
    system_prompt: str
    vision_prompt: str
    temperature: float = 1.3

    def __post_init__(self) -> None:
        # 初始化 SDK 客户端
        self._client = ZhipuAiClient(api_key=self.api_key)

    async def ask(self, image_url: str , prompt: str | None = None ) -> str:
        """传入图片 URL，返回模型对图片的短评/描述。"""
        if not self.api_key:
            return "未配置 ZHIPU_API_KEY"

        def _call():
            # 同步调用放到线程里执行
            print("📌 开始调用智谱AI接口")
            if prompt is None:
                final_prompt = f"{self.system_prompt},{self.vision_prompt} 请评价一下这张图片，简短一点，不要超过100个字。"
            else:
                final_prompt = prompt

            return self._client.chat.completions.create(
                model="glm-4.6v",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"{final_prompt}"
                                ),
                            },
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                temperature=self.temperature,
            )

        try:
            response = await asyncio.to_thread(_call)
            clean_text = response.choices[0].message.content.strip()
            return clean_text
        except Exception as e:
            print(f"❌ 视觉 AI 出错: {e}")
            return "图片加载失败了捏..."
