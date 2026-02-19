"""情绪识别与机器人情绪更新。

职责：
- EmotionRecognizer: 从文本识别用户情绪（规则 baseline + LLM 增强）
- update_bot_vad: 根据用户情绪、关系等更新机器人 VAD 状态
"""

from __future__ import annotations

import logging
import re
from typing import Optional, TYPE_CHECKING

from .models import UserEmotion, BotEmotionState, RelationState

if TYPE_CHECKING:
    from ..ai.siliconflow import SiliconFlowEmotionClient

logger = logging.getLogger(__name__)


class EmotionRecognizer:
    """情绪识别器（规则 baseline + 可选 LLM 增强）。

    支持两种模式：
    1. 规则模式（默认）：基于关键词匹配，快速但准确度有限
    2. LLM 增强模式：使用 SiliconFlow API，准确度更高但需要网络请求
    """

    # LLM 客户端（可选）
    _llm_client: Optional["SiliconFlowEmotionClient"] = None
    _use_llm: bool = False

    # 关键词 -> (label, intensity_boost)
    EMOTION_KEYWORDS = {
        # happy
        "开心": ("happy", 0.7),
        "高兴": ("happy", 0.7),
        "快乐": ("happy", 0.7),
        "好棒": ("happy", 0.6),
        "太好了": ("happy", 0.7),
        "哈哈": ("happy", 0.6),
        "嘻嘻": ("happy", 0.5),
        "233": ("happy", 0.5),
        "666": ("happy", 0.5),
        "厉害": ("happy", 0.5),
        "爱你": ("happy", 0.8),
        "喜欢": ("happy", 0.6),
        "❤": ("happy", 0.6),
        "😊": ("happy", 0.6),
        "😄": ("happy", 0.7),
        "🥰": ("happy", 0.7),

        # sad
        "难过": ("sad", 0.7),
        "伤心": ("sad", 0.7),
        "悲伤": ("sad", 0.8),
        "哭了": ("sad", 0.6),
        "呜呜": ("sad", 0.6),
        "555": ("sad", 0.5),
        "郁闷": ("sad", 0.6),
        "不开心": ("sad", 0.6),
        "😢": ("sad", 0.7),
        "😭": ("sad", 0.8),
        "💔": ("sad", 0.6),

        # angry
        "生气": ("angry", 0.7),
        "愤怒": ("angry", 0.8),
        "烦死了": ("angry", 0.7),
        "讨厌": ("angry", 0.6),
        "滚": ("angry", 0.7),
        "傻逼": ("angry", 0.8),
        "垃圾": ("angry", 0.6),
        "去死": ("angry", 0.9),
        "😠": ("angry", 0.7),
        "😡": ("angry", 0.8),
        "🤬": ("angry", 0.9),

        # fear
        "害怕": ("fear", 0.7),
        "恐惧": ("fear", 0.8),
        "吓人": ("fear", 0.6),
        "可怕": ("fear", 0.6),
        "😨": ("fear", 0.7),
        "😱": ("fear", 0.8),

        # disgust
        "恶心": ("disgust", 0.7),
        "讨厌": ("disgust", 0.6),
        "呕": ("disgust", 0.6),
        "🤮": ("disgust", 0.8),
        "🤢": ("disgust", 0.7),

        # surprise
        "惊讶": ("surprise", 0.7),
        "震惊": ("surprise", 0.8),
        "天哪": ("surprise", 0.6),
        "卧槽": ("surprise", 0.6),
        "我靠": ("surprise", 0.6),
        "😮": ("surprise", 0.6),
        "😲": ("surprise", 0.7),
        "🤯": ("surprise", 0.8),

        # calm
        "平静": ("calm", 0.7),
        "淡定": ("calm", 0.7),
        "冷静": ("calm", 0.6),
        "没事": ("calm", 0.5),
        "还好": ("calm", 0.5),
        "😌": ("calm", 0.6),
    }

    # 标点符号情绪增强
    PUNCTUATION_BOOST = {
        "！": 0.1,
        "!": 0.1,
        "？": 0.05,
        "?": 0.05,
        "~": 0.05,
        "。": -0.05,
    }

    def __init__(self, llm_client: Optional["SiliconFlowEmotionClient"] = None):
        """初始化情绪识别器。

        参数:
            llm_client: SiliconFlow 情绪识别客户端（可选）
        """
        self._llm_client = llm_client
        self._use_llm = llm_client is not None

    def set_llm_client(self, client: "SiliconFlowEmotionClient") -> None:
        """设置 LLM 客户端。"""
        self._llm_client = client
        self._use_llm = True

    def disable_llm(self) -> None:
        """禁用 LLM 模式。"""
        self._use_llm = False

    def enable_llm(self) -> None:
        """启用 LLM 模式（需要已设置客户端）。"""
        if self._llm_client:
            self._use_llm = True

    async def recognize_async(self, text: str) -> UserEmotion:
        """异步识别情绪（优先使用 LLM，降级到规则）。

        性能优化：短文本或高置信度规则匹配时跳过 LLM。
        """
        if not text or not text.strip():
            return UserEmotion(label="neutral", intensity=0.3, confidence=0.9)

        # 性能优化：短文本直接用规则
        if len(text) < 10:
            result = self.recognize(text)
            return result

        # 先尝试规则识别
        rule_result = self.recognize(text)

        # 如果规则识别置信度足够高，跳过 LLM
        if rule_result.confidence >= 0.7 and rule_result.label != "neutral":
            logger.debug("emotion rules-fast -> %s", rule_result.label)
            return rule_result

        # 尝试使用 LLM
        if self._use_llm and self._llm_client:
            try:
                label, intensity, confidence = await self._llm_client.recognize_emotion(text)
                logger.debug("emotion llm -> %s", label)
                return UserEmotion(label=label, intensity=intensity, confidence=confidence)
            except Exception as e:
                logger.warning("emotion llm failed, fallback rules: %s", e)

        # 降级到规则识别结果
        logger.debug("emotion rules -> %s", rule_result.label)
        return rule_result

    def recognize(self, text: str) -> UserEmotion:
        """识别文本中的情绪。

        返回:
            UserEmotion: 包含 label, intensity, confidence
        """
        if not text or not text.strip():
            return UserEmotion(label="neutral", intensity=0.3, confidence=0.9)

        text_lower = text.lower()

        # 统计各情绪的命中
        emotion_scores: dict[str, float] = {}
        hit_count = 0

        for keyword, (label, intensity) in self.EMOTION_KEYWORDS.items():
            if keyword in text_lower or keyword in text:
                if label not in emotion_scores:
                    emotion_scores[label] = 0.0
                emotion_scores[label] += intensity
                hit_count += 1

        # 没有命中任何关键词，返回 neutral
        if not emotion_scores:
            return UserEmotion(label="neutral", intensity=0.3, confidence=0.5)

        # 找最高分的情绪
        best_label = max(emotion_scores, key=lambda k: emotion_scores[k])
        base_intensity = min(1.0, emotion_scores[best_label])

        # 标点符号调整
        punct_boost = 0.0
        for punct, boost in self.PUNCTUATION_BOOST.items():
            punct_boost += text.count(punct) * boost
        base_intensity = max(0.1, min(1.0, base_intensity + punct_boost))

        # 置信度基于命中数量
        confidence = min(0.9, 0.4 + hit_count * 0.15)

        return UserEmotion(
            label=best_label,
            intensity=round(base_intensity, 2),
            confidence=round(confidence, 2),
        )


# 用户情绪 label -> VAD 偏移（粗略映射）
EMOTION_TO_VAD_DELTA = {
    "neutral": (0.0, 0.0, 0.0),
    "happy": (0.3, 0.2, 0.1),
    "sad": (-0.2, -0.1, -0.1),
    "angry": (-0.2, 0.3, 0.2),
    "fear": (-0.3, 0.2, -0.2),
    "disgust": (-0.2, 0.1, 0.1),
    "surprise": (0.1, 0.3, 0.0),
    "calm": (0.1, -0.2, 0.1),
}


def update_bot_vad(
    prev_vad: BotEmotionState,
    user_emotion: UserEmotion,
    relation: Optional[RelationState] = None,
    decay_alpha: float = 0.7,
) -> BotEmotionState:
    """更新机器人 VAD 情绪状态。

    参数:
        prev_vad: 上一轮的 VAD 状态
        user_emotion: 当前用户情绪
        relation: 用户关系状态（可选）
        decay_alpha: 衰减/惯性系数（0~1），越大惯性越强

    返回:
        新的 BotEmotionState
    """
    # 获取用户情绪对应的 VAD 偏移
    delta = EMOTION_TO_VAD_DELTA.get(user_emotion.label, (0.0, 0.0, 0.0))
    delta_v, delta_a, delta_d = delta

    # 根据用户情绪强度缩放偏移（避免镜像效应）
    scale = user_emotion.intensity * 0.3  # 小权重
    delta_v *= scale
    delta_a *= scale
    delta_d *= scale

    # 关系影响：熟悉度高 -> 更稳定，信任高 -> D 更高
    if relation:
        # 熟悉度提高稳定性（减少波动）
        stability_factor = 0.5 + relation.familiarity * 0.5
        delta_v *= (1.0 - relation.familiarity * 0.3)
        delta_a *= (1.0 - relation.familiarity * 0.3)

        # 信任度轻微影响 D
        delta_d += relation.trust * 0.05

    # 计算目标值（基线 + delta）
    target_v = prev_vad.V0 + delta_v
    target_a = prev_vad.A0 + delta_a
    target_d = prev_vad.D0 + delta_d

    # 惯性衰减：new = alpha * prev + (1-alpha) * target
    new_v = decay_alpha * prev_vad.V + (1 - decay_alpha) * target_v
    new_a = decay_alpha * prev_vad.A + (1 - decay_alpha) * target_a
    new_d = decay_alpha * prev_vad.D + (1 - decay_alpha) * target_d

    new_state = BotEmotionState(
        V=new_v,
        A=new_a,
        D=new_d,
        V0=prev_vad.V0,
        A0=prev_vad.A0,
        D0=prev_vad.D0,
    )
    new_state.clamp()
    return new_state
