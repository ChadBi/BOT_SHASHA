"""DeepSeek 文本模型封装。"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


@dataclass
class DeepSeekText:
    """DeepSeek 文本聊天客户端。"""

    api_key: str
    base_url: str
    system_prompt: str
    temperature: float = 1.3
    max_tokens: int = 50
    retry_attempts: int = 2
    retry_base_delay: float = 0.4
    fail_threshold: int = 3
    cooldown_seconds: int = 30

    _fail_count: int = field(default=0, init=False)
    _circuit_open_until: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _is_circuit_open(self) -> bool:
        return time.time() < self._circuit_open_until

    def _on_success(self) -> None:
        self._fail_count = 0

    def _on_failure(self) -> None:
        self._fail_count += 1
        if self._fail_count >= self.fail_threshold:
            self._circuit_open_until = time.time() + self.cooldown_seconds
            logger.warning("deepseek circuit open for %ss", self.cooldown_seconds)

    async def _chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None) -> str:
        if not self.api_key:
            return "未配置 DEEPSEEK_API_KEY"

        if self._is_circuit_open():
            return "现在有点忙，稍后再找我聊聊吧~"

        attempts = max(1, self.retry_attempts + 1)
        for i in range(attempts):
            try:
                response = await self._client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    stream=False,
                    temperature=self.temperature,
                    max_tokens=max_tokens or self.max_tokens,
                )
                self._on_success()
                return response.choices[0].message.content
            except Exception as e:
                self._on_failure()
                if i == attempts - 1:
                    logger.error("deepseek error after retries: %s", e)
                    return "脑子瓦特了..."
                await asyncio.sleep(self.retry_base_delay * (2**i))

        return "脑子瓦特了..."

    async def ask(self, question: str) -> str:
        return await self._chat(
            [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": question},
            ]
        )

    async def ask_with_context(
        self,
        question: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """带上下文的多轮对话。

        参数:
            question: 当前问题
            system_prompt: 自定义系统提示词（可选，默认用初始化时的）
            history: 历史消息列表 [{"role": "user"/"assistant", "content": "..."}]
            max_tokens: 自定义最大 token 数（可选）

        返回:
            模型回复文本
        """
        if not self.api_key:
            return "未配置 DEEPSEEK_API_KEY"

        try:
            messages = []

            # 系统提示词
            sys_prompt = system_prompt or self.system_prompt
            messages.append({"role": "system", "content": sys_prompt})

            # 历史消息
            if history:
                messages.extend(history)

            # 当前问题
            messages.append({"role": "user", "content": question})

            # 计算 prompt 长度（用于日志）
            prompt_length = sum(len(m.get("content", "")) for m in messages)
            logger.info("[deepseek] req messages=%s chars=%s", len(messages), prompt_length)
            reply = await self._chat(messages, max_tokens=max_tokens)
            logger.info("[deepseek] resp chars=%s", len(reply))
            return reply

        except Exception as e:
            logger.error("[deepseek] multi-turn error: %s", e)
            return "脑子瓦特了..."

    async def ask_with_messages(self, messages: List[Dict[str, str]]) -> str:
        """直接传入完整的消息列表。

        参数:
            messages: 完整消息列表（包含 system/user/assistant）

        返回:
            模型回复文本
        """
        return await self._chat(messages)
