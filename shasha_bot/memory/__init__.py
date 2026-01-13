"""记忆与情绪模块。

本模块提供：
- UserMemoryState: 用户记忆状态（短期记忆、人格、自述等）
- BotEmotionState: 机器人情绪状态（VAD模型）
- RelationState: 用户关系状态
- EmotionRecognizer: 用户情绪识别
- MemoryManager: 统一管理接口
- prompt 工具函数: 构建系统上下文
"""

from .models import (
    UserMemoryState,
    UserProfile,
    UserCounters,
    BotEmotionState,
    RelationState,
    STMMessage,
    UserEmotion,
    PersonalityFactors,
)
from .emotion import EmotionRecognizer, update_bot_vad
from .manager import MemoryManager, MemoryConfig
from .prompt import (
    build_system_context,
    build_chat_messages,
    format_memory_summary,
)

__all__ = [
    "UserMemoryState",
    "UserProfile",
    "UserCounters",
    "BotEmotionState",
    "RelationState",
    "STMMessage",
    "UserEmotion",
    "PersonalityFactors",
    "EmotionRecognizer",
    "update_bot_vad",
    "MemoryManager",
    "MemoryConfig",
    "build_system_context",
    "build_chat_messages",
    "format_memory_summary",
]
