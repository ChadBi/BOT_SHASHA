"""DeepSeek 文本模型封装。

把 OpenAI 兼容接口包一层，统一成：await ask(text) -> str
支持多轮对话：await ask_with_history(messages) -> str
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from openai import AsyncOpenAI
import json

logger = logging.getLogger(__name__)


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
            print(f"[deepseek] req messages={len(messages)} chars={prompt_length}")
            # print(json.dumps(messages, ensure_ascii=False, indent=2))
            response = await self._client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=False,
                temperature=self.temperature,
                max_tokens=max_tokens or self.max_tokens,
            )
            
            reply = response.choices[0].message.content
            print(f"[deepseek] resp chars={len(reply)}")
            return reply
            
        except Exception as e:
            print(f"[deepseek] multi-turn error: {e}")
            return "脑子瓦特了..."

    async def ask_with_messages(self, messages: List[Dict[str, str]]) -> str:
        """直接传入完整的消息列表。
        
        参数:
            messages: 完整消息列表（包含 system/user/assistant）
            
        返回:
            模型回复文本
        """
        if not self.api_key:
            return "未配置 DEEPSEEK_API_KEY"
        # print(json.dumps(messages, ensure_ascii=False, indent=2))
        
        try:
            response = await self._client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=False,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[deepseek] ask_with_messages error: {e}")
            return "脑子瓦特了..."
