"""SiliconFlow 情绪识别模块。

使用 Qwen2.5-7B 模型进行情绪识别，
作为规则引擎的增强方案。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Tuple

import httpx

logger = logging.getLogger(__name__)

# 情绪识别系统提示词
EMOTION_SYSTEM_PROMPT = """你是一个情绪分析专家。请分析用户消息中的情绪。

你必须从以下 8 种情绪中选择一个最匹配的：
- neutral（中性/平静）
- happy（开心/愉快）
- sad（难过/悲伤）
- angry（生气/愤怒）
- fear（害怕/恐惧）
- disgust（厌恶/反感）
- surprise（惊讶/意外）
- calm（平和/安宁）

请用 JSON 格式返回，包含以下字段：
- label: 情绪标签（上面 8 个之一）
- intensity: 情绪强度（0.0-1.0 的浮点数）
- reason: 简短的判断理由（不超过 20 字）

只返回 JSON，不要有其他内容。

示例输出：
{"label": "happy", "intensity": 0.8, "reason": "使用了开心的表情和感叹词"}
"""


@dataclass
class SiliconFlowEmotionClient:
    """SiliconFlow 情绪识别客户端。"""

    api_key: str
    base_url: str = "https://api.siliconflow.cn/v1/chat/completions"
    model: str = "Qwen/Qwen2.5-7B-Instruct"
    timeout: float = 10.0

    async def recognize_emotion(self, text: str) -> Tuple[str, float, float]:
        """识别文本情绪。

        返回:
            Tuple[label, intensity, confidence]
        """
        if not text or not text.strip():
            return ("neutral", 0.3, 0.9)

        if not self.api_key:
            logger.info("siliconflow API key 未配置，使用默认情绪")
            return ("neutral", 0.5, 0.5)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.base_url,
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": EMOTION_SYSTEM_PROMPT},
                            {"role": "user", "content": f"请分析以下消息的情绪：\n\n{text}"},
                        ],
                        "stream": False,
                        "max_tokens": 100,
                        "temperature": 0.3,
                        "top_p": 0.9,
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()

                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # 解析 JSON 响应
                result = self._parse_emotion_response(content)
                logger.debug("siliconflow emotion recognized: %s", result[0])
                return result

        except httpx.TimeoutException:
            logger.warning("siliconflow timeout")
            return ("neutral", 0.5, 0.3)
        except Exception as e:
            logger.warning("siliconflow error: %s", e)
            return ("neutral", 0.5, 0.3)

    def _parse_emotion_response(self, content: str) -> Tuple[str, float, float]:
        """解析模型返回的 JSON 响应。"""
        valid_labels = {"neutral", "happy", "sad", "angry", "fear", "disgust", "surprise", "calm"}

        try:
            # 尝试提取 JSON
            content = content.strip()
            if content.startswith("```"):
                # 移除 markdown 代码块
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            result = json.loads(content)

            label = result.get("label", "neutral")
            if label not in valid_labels:
                label = "neutral"

            intensity = float(result.get("intensity", 0.5))
            intensity = max(0.0, min(1.0, intensity))

            # 模型返回的置信度较高
            confidence = 0.8

            return (label, intensity, confidence)

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("siliconflow parse failed: %s", e)
            return ("neutral", 0.5, 0.4)
