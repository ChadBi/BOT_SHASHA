"""记忆与情绪数据模型。

定义核心数据结构，用于存储用户记忆、情绪状态等。
所有模型都是 dataclass，支持序列化到 JSON。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class STMMessage:
    """短期记忆中的单条消息。"""
    role: str  # "user" 或 "bot"
    text: str
    ts: float = field(default_factory=time.time)
    meta: Dict[str, Any] = field(default_factory=dict)  # 可选：has_image, group_id 等

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "STMMessage":
        return cls(
            role=data.get("role", "user"),
            text=data.get("text", ""),
            ts=data.get("ts", time.time()),
            meta=data.get("meta", {}),
        )


@dataclass
class PersonalityFactors:
    """人格因子（0~1）。"""
    talkative: float = 0.5   # 话多程度
    optimism: float = 0.5    # 乐观程度
    stability: float = 0.5   # 情绪稳定性
    politeness: float = 0.5  # 礼貌程度

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonalityFactors":
        return cls(
            talkative=float(data.get("talkative", 0.5)),
            optimism=float(data.get("optimism", 0.5)),
            stability=float(data.get("stability", 0.5)),
            politeness=float(data.get("politeness", 0.5)),
        )


@dataclass
class UserProfile:
    """用户个人资料。"""
    nickname: str = ""  # 默认为 QQ 昵称，可被命令覆盖
    self_descriptions: List[str] = field(default_factory=list)  # 用户手动描述

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nickname": self.nickname,
            "self_descriptions": self.self_descriptions.copy(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        return cls(
            nickname=data.get("nickname", ""),
            self_descriptions=data.get("self_descriptions", []),
        )


@dataclass
class UserCounters:
    """用户统计计数器。"""
    total_msgs: int = 0
    new_msgs_since_last_summary: int = 0
    last_summary_ts: float = 0.0
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserCounters":
        return cls(
            total_msgs=data.get("total_msgs", 0),
            new_msgs_since_last_summary=data.get("new_msgs_since_last_summary", 0),
            last_summary_ts=data.get("last_summary_ts", 0.0),
            version=data.get("version", 1),
        )


@dataclass
class UserMemoryState:
    """用户记忆状态（完整）。"""
    user_id: str
    profile: UserProfile = field(default_factory=UserProfile)
    personality: PersonalityFactors = field(default_factory=PersonalityFactors)
    short_term_memory: List[STMMessage] = field(default_factory=list)
    long_term_memory: List[Dict[str, Any]] = field(default_factory=list)  # LTM 存储重要事件
    counters: UserCounters = field(default_factory=UserCounters)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "profile": self.profile.to_dict(),
            "personality": self.personality.to_dict(),
            "short_term_memory": [m.to_dict() for m in self.short_term_memory],
            "long_term_memory": self.long_term_memory,
            "counters": self.counters.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserMemoryState":
        return cls(
            user_id=str(data.get("user_id", "")),
            profile=UserProfile.from_dict(data.get("profile", {})),
            personality=PersonalityFactors.from_dict(data.get("personality", {})),
            short_term_memory=[
                STMMessage.from_dict(m) for m in data.get("short_term_memory", [])
            ],
            long_term_memory=data.get("long_term_memory", []),
            counters=UserCounters.from_dict(data.get("counters", {})),
        )


@dataclass
class RelationState:
    """机器人与用户的关系状态。"""
    user_id: str
    familiarity: float = 0.1   # 熟悉度 0~1
    trust: float = 0.5         # 信任度 0~1
    last_interaction_ts: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelationState":
        return cls(
            user_id=str(data.get("user_id", "")),
            familiarity=float(data.get("familiarity", 0.1)),
            trust=float(data.get("trust", 0.5)),
            last_interaction_ts=float(data.get("last_interaction_ts", 0.0)),
        )


@dataclass
class UserEmotion:
    """用户情绪识别结果。"""
    label: str = "neutral"  # neutral, happy, sad, angry, fear, disgust, surprise, calm
    intensity: float = 0.5  # 0~1
    confidence: float = 0.5  # 0~1

    VALID_LABELS = ("neutral", "happy", "sad", "angry", "fear", "disgust", "surprise", "calm")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserEmotion":
        label = data.get("label", "neutral")
        if label not in cls.VALID_LABELS:
            label = "neutral"
        return cls(
            label=label,
            intensity=max(0.0, min(1.0, float(data.get("intensity", 0.5)))),
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
        )


@dataclass
class BotEmotionState:
    """机器人情绪状态（VAD模型）。

    V (Valence): 效价，-1（消极）~ +1（积极）
    A (Arousal): 唤醒度，0（平静）~ 1（激动）
    D (Dominance): 支配度，0（顺从）~ 1（支配）
    """
    V: float = 0.3   # 初始偏向积极
    A: float = 0.3   # 初始偏向平静
    D: float = 0.5   # 中等支配度

    # 基线（用于衰减回归）
    V0: float = 0.3
    A0: float = 0.3
    D0: float = 0.5

    def clamp(self) -> None:
        """限幅到合法范围。"""
        self.V = max(-1.0, min(1.0, self.V))
        self.A = max(0.0, min(1.0, self.A))
        self.D = max(0.0, min(1.0, self.D))

    def to_dict(self) -> Dict[str, float]:
        return {
            "V": self.V,
            "A": self.A,
            "D": self.D,
            "V0": self.V0,
            "A0": self.A0,
            "D0": self.D0,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotEmotionState":
        state = cls(
            V=float(data.get("V", 0.3)),
            A=float(data.get("A", 0.3)),
            D=float(data.get("D", 0.5)),
            V0=float(data.get("V0", 0.3)),
            A0=float(data.get("A0", 0.3)),
            D0=float(data.get("D0", 0.5)),
        )
        state.clamp()
        return state

    def get_suggested_tone(self) -> str:
        """根据 VAD 状态返回建议的语气描述。"""
        if self.V > 0.5 and self.A > 0.5:
            return "热情活泼"
        elif self.V > 0.3 and self.A < 0.4:
            return "温和平静"
        elif self.V < -0.3 and self.A > 0.5:
            return "急躁不安"
        elif self.V < -0.3 and self.A < 0.4:
            return "低落消沉"
        elif self.V > 0.3:
            return "友好积极"
        elif self.V < -0.1:
            return "略显疲惫"
        else:
            return "平稳中性"
