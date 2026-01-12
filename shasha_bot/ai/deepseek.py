"""DeepSeek 文本模型封装。

把 OpenAI 兼容接口包一层，统一成：await ask(text) -> str
"""

from __future__ import annotations

from dataclasses import dataclass
from openai import AsyncOpenAI


@dataclass
class DeepSeekText:
    """DeepSeek 文本聊天客户端。"""
    api_key: str
    base_url: str
    system_prompt: str
    temperature: float = 1.3
    max_tokens: int = 50

    def __post_init__(self) -> None:
        # AsyncOpenAI 兼容 deepseek-chat
        self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def ask(self, question: str) -> str:
        """向模型提问并返回文本回复（失败时返回兜底文本）。"""
        if not self.api_key:
            return "未配置 DEEPSEEK_API_KEY"
        try:
            response = await self._client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": question},
                ],
                stream=False,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ 文本 AI 出错: {e}")
            return "脑子瓦特了..."
