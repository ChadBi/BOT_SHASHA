"""智谱视觉模型封装。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from zai import ZhipuAiClient

logger = logging.getLogger(__name__)


@dataclass
class ZhipuVision:
    """图片评价/描述（视觉模型）。"""

    api_key: str
    system_prompt: str
    vision_prompt: str
    temperature: float = 1.3
    retry_attempts: int = 2
    retry_base_delay: float = 0.4

    def __post_init__(self) -> None:
        self._client = ZhipuAiClient(api_key=self.api_key)

    async def ask(self, image_url: str, prompt: str | None = None) -> str:
        if not self.api_key:
            return "未配置 ZHIPU_API_KEY"

        def _call(final_prompt: str):
            return self._client.chat.completions.create(
                model="glm-4.6v",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": final_prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                temperature=self.temperature,
            )

        final_prompt = (
            prompt
            or f"{self.system_prompt},{self.vision_prompt} 请评价一下这张图片，简短一点，不要超过100个字。"
        )

        attempts = max(1, self.retry_attempts + 1)
        for i in range(attempts):
            try:
                response = await asyncio.to_thread(_call, final_prompt)
                return response.choices[0].message.content.strip()
            except Exception as e:
                if i == attempts - 1:
                    logger.error("zhipu vision error after retries: %s", e)
                    return "图片加载失败了捏..."
                await asyncio.sleep(self.retry_base_delay * (2**i))

        return "图片加载失败了捏..."
