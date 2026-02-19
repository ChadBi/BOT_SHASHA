"""记忆管理器。

统一管理用户记忆、关系状态、情绪状态的读写操作。
提供简洁的接口给外部调用。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, Optional

from .models import (
    UserMemoryState,
    UserProfile,
    PersonalityFactors,
    UserCounters,
    STMMessage,
    RelationState,
    BotEmotionState,
    UserEmotion,
)
from .storage import Storage
from .emotion import EmotionRecognizer, update_bot_vad

logger = logging.getLogger(__name__)

# 导入 MemorySettings 作为 MemoryConfig 的别名（向后兼容）
from ..settings import MemorySettings

# 向后兼容：旧代码可能使用 MemoryConfig
MemoryConfig = MemorySettings


class MemoryManager:
    """记忆管理器。

    职责：
    - 管理用户记忆状态（UserMemoryState）
    - 管理用户关系（RelationState）
    - 管理机器人情绪（BotEmotionState）
    - 提供情绪识别（EmotionRecognizer）

    配置通过 MemorySettings 传入（来自 BotSettings.memory）。
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        config: Optional["MemorySettings"] = None,  # forward reference
    ):
        """初始化记忆管理器。

        参数:
            data_dir: 数据存储目录
            config: MemorySettings 配置（来自 BotSettings.memory）
        """
        if data_dir is None:
            data_dir = Path("shasha_bot/memory_data")
        self.storage = Storage(data_dir)
        self.config = config
        self._emotion_recognizer: Optional[EmotionRecognizer] = None

        # 内存缓存（减少磁盘 I/O）
        self._user_cache: Dict[str, UserMemoryState] = {}
        self._relation_cache: Dict[str, RelationState] = {}
        self._bot_emotion: BotEmotionState = BotEmotionState()

    @property
    def emotion_recognizer(self) -> EmotionRecognizer:
        """获取情绪识别器（懒加载）。"""
        if self._emotion_recognizer is None:
            self._emotion_recognizer = EmotionRecognizer()
        return self._emotion_recognizer

    @emotion_recognizer.setter
    def emotion_recognizer(self, value: EmotionRecognizer) -> None:
        """设置情绪识别器（支持注入带 LLM 的版本）。"""
        self._emotion_recognizer = value

    async def get_user_state(self, user_id: str) -> UserMemoryState:
        """获取用户记忆状态（带缓存）。"""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        data = await self.storage.load_user(user_id)
        if data and "user_id" in data:
            state = UserMemoryState.from_dict(data)
        else:
            state = UserMemoryState(user_id=user_id)

        self._user_cache[user_id] = state
        return state

    async def save_user_state(self, user_id: str) -> bool:
        """保存用户记忆状态。"""
        if user_id not in self._user_cache:
            return True  # 无需保存

        state = self._user_cache[user_id]
        return await self.storage.save_user(user_id, state.to_dict())

    async def get_relation(self, user_id: str) -> RelationState:
        """获取用户关系状态。"""
        if user_id in self._relation_cache:
            return self._relation_cache[user_id]

        # 尝试从用户数据中读取
        data = await self.storage.load_user(user_id)
        if data and "relation" in data:
            relation = RelationState.from_dict(data["relation"])
        else:
            relation = RelationState(user_id=user_id)

        self._relation_cache[user_id] = relation
        return relation

    async def save_relation(self, user_id: str) -> bool:
        """保存用户关系状态（合并到用户数据中）。"""
        if user_id not in self._relation_cache:
            return True

        relation = self._relation_cache[user_id]

        # 合并到用户数据
        data = await self.storage.load_user(user_id)
        data["relation"] = relation.to_dict()
        return await self.storage.save_user(user_id, data)

    def get_bot_emotion(self) -> BotEmotionState:
        """获取机器人当前情绪状态。"""
        return self._bot_emotion

    def set_bot_emotion(self, state: BotEmotionState) -> None:
        """设置机器人情绪状态。"""
        self._bot_emotion = state

    # ================= 短期记忆操作 =================

    async def append_to_stm(
        self,
        user_id: str,
        role: str,
        text: str,
        meta: Optional[Dict] = None,
    ) -> None:
        """追加消息到短期记忆。"""
        state = await self.get_user_state(user_id)

        msg = STMMessage(
            role=role,
            text=text,
            ts=time.time(),
            meta=meta or {},
        )
        state.short_term_memory.append(msg)

        # 保持最大轮数
        while len(state.short_term_memory) > self.config.stm_max_turns:
            state.short_term_memory.pop(0)

        # 更新计数器
        if role == "user":
            state.counters.total_msgs += 1
            state.counters.new_msgs_since_last_summary += 1

        # 异步保存（不阻塞）
        await self.save_user_state(user_id)

    def get_stm(self, user_id: str) -> list[STMMessage]:
        """获取短期记忆（同步版，需先调用 get_user_state）。"""
        if user_id in self._user_cache:
            return self._user_cache[user_id].short_term_memory
        return []

    # ================= 用户资料操作 =================

    async def set_nickname(self, user_id: str, nickname: str) -> None:
        """设置用户昵称。"""
        state = await self.get_user_state(user_id)
        state.profile.nickname = nickname
        await self.save_user_state(user_id)
        logger.info("用户 %s 昵称已设置", user_id)

    async def add_self_description(self, user_id: str, desc: str) -> bool:
        """添加用户自述（返回是否成功）。"""
        state = await self.get_user_state(user_id)

        # 检查数量限制
        if len(state.profile.self_descriptions) >= self.config.max_self_descriptions:
            # 移除最早的一条
            state.profile.self_descriptions.pop(0)

        state.profile.self_descriptions.append(desc)
        await self.save_user_state(user_id)
        logger.info("用户 %s 添加自述", user_id)
        return True

    async def clear_self_descriptions(self, user_id: str) -> None:
        """清除用户自述。"""
        state = await self.get_user_state(user_id)
        state.profile.self_descriptions.clear()
        await self.save_user_state(user_id)
        logger.info("用户 %s 自述已清除", user_id)

    async def clear_stm(self, user_id: str) -> None:
        """清除短期记忆。"""
        state = await self.get_user_state(user_id)
        state.short_term_memory.clear()
        await self.save_user_state(user_id)
        logger.info("用户 %s 短期记忆已清除", user_id)

    # ================= 关系更新 =================

    async def update_relation_on_interaction(self, user_id: str) -> None:
        """交互时更新关系状态。"""
        relation = await self.get_relation(user_id)

        # 增加熟悉度
        relation.familiarity = min(
            1.0, relation.familiarity + self.config.familiarity_step
        )
        relation.last_interaction_ts = time.time()

        await self.save_relation(user_id)

    async def update_relation_on_negative_emotion(
        self, user_id: str, intensity: float
    ) -> None:
        """用户负面情绪时轻微影响信任度。"""
        relation = await self.get_relation(user_id)

        # 只有高强度负面情绪才影响
        if intensity > 0.6:
            relation.trust = max(
                0.1, relation.trust - self.config.trust_step * intensity
            )
            await self.save_relation(user_id)

    # ================= 情绪处理 =================

    def recognize_emotion(self, text: str) -> UserEmotion:
        """识别用户情绪。"""
        return self.emotion_recognizer.recognize(text)

    async def update_bot_emotion(
        self, user_emotion: UserEmotion, user_id: Optional[str] = None
    ) -> BotEmotionState:
        """更新机器人情绪状态。"""
        relation = None
        if user_id:
            relation = await self.get_relation(user_id)

        new_state = update_bot_vad(
            prev_vad=self._bot_emotion,
            user_emotion=user_emotion,
            relation=relation,
            decay_alpha=self.config.emotion_decay_alpha,
        )
        self._bot_emotion = new_state
        return new_state

    # ================= 人格总结（触发判断） =================

    async def should_update_personality(self, user_id: str) -> bool:
        """判断是否应该触发人格总结。"""
        state = await self.get_user_state(user_id)
        counters = state.counters

        # 条件 1：新消息数达到阈值
        if counters.new_msgs_since_last_summary < self.config.personality_update_min_msgs:
            return False

        # 条件 2：冷却时间已过
        cooldown_seconds = self.config.personality_update_cooldown_hours * 3600
        if time.time() - counters.last_summary_ts < cooldown_seconds:
            return False

        return True

    async def mark_personality_updated(self, user_id: str) -> None:
        """标记人格总结已完成。"""
        state = await self.get_user_state(user_id)
        state.counters.new_msgs_since_last_summary = 0
        state.counters.last_summary_ts = time.time()
        await self.save_user_state(user_id)

    async def update_personality(
        self, user_id: str, factors: PersonalityFactors
    ) -> None:
        """更新用户人格因子。"""
        state = await self.get_user_state(user_id)
        state.personality = factors
        await self.mark_personality_updated(user_id)
        logger.info("用户 %s 人格因子已更新", user_id)

    # ================= 便捷查询 =================

    async def get_user_summary(self, user_id: str) -> Dict:
        """获取用户摘要信息（用于调试/查看）。"""
        state = await self.get_user_state(user_id)
        relation = await self.get_relation(user_id)

        return {
            "user_id": user_id,
            "nickname": state.profile.nickname,
            "self_descriptions": state.profile.self_descriptions[-3:],  # 最近 3 条
            "personality": state.personality.to_dict(),
            "stm_length": len(state.short_term_memory),
            "total_msgs": state.counters.total_msgs,
            "relation": {
                "familiarity": round(relation.familiarity, 3),
                "trust": round(relation.trust, 3),
            },
            "ltm_count": len(state.long_term_memory) if hasattr(state, 'long_term_memory') else 0,
        }

    # ================= 人格因子自动总结 (P1.2) =================

    def build_personality_analysis_prompt(self, stm: list) -> str:
        """构建人格分析的 prompt。"""
        # 提取用户消息
        user_messages = [m.text for m in stm if m.role == "user"][-20:]  # 最近 20 条
        if not user_messages:
            return ""

        conversation_text = "\n".join([f"- {msg}" for msg in user_messages])

        return f"""请分析以下用户消息，推断其人格特征。

用户消息：
{conversation_text}

请用 JSON 格式返回人格因子（0.0-1.0 范围）：
- talkative: 话多程度（消息长度、频率）
- optimism: 乐观程度（正面词汇、积极态度）
- stability: 情绪稳定性（情绪波动、激动程度）
- politeness: 礼貌程度（敬语、友好表达）

只返回 JSON，格式如：{{"talkative": 0.6, "optimism": 0.7, "stability": 0.5, "politeness": 0.8}}"""

    async def analyze_personality_with_llm(
        self, user_id: str, llm_client
    ) -> Optional[PersonalityFactors]:
        """使用 LLM 分析用户人格因子。

        参数:
            user_id: 用户 ID
            llm_client: DeepSeek 客户端

        返回:
            PersonalityFactors 或 None（分析失败时）
        """
        import json as json_module

        state = await self.get_user_state(user_id)
        stm = state.short_term_memory

        if len(stm) < 10:
            logger.debug("用户 %s 消息不足，跳过人格分析", user_id)
            return None

        prompt = self.build_personality_analysis_prompt(stm)
        if not prompt:
            return None

        try:
            response = await llm_client.ask(prompt)

            # 解析 JSON
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            data = json_module.loads(response)

            factors = PersonalityFactors(
                talkative=max(0.0, min(1.0, float(data.get("talkative", 0.5)))),
                optimism=max(0.0, min(1.0, float(data.get("optimism", 0.5)))),
                stability=max(0.0, min(1.0, float(data.get("stability", 0.5)))),
                politeness=max(0.0, min(1.0, float(data.get("politeness", 0.5)))),
            )

            logger.info("用户 %s 人格分析完成", user_id)
            return factors

        except Exception as e:
            logger.warning("用户 %s 人格分析失败：%s", user_id, e)
            return None

    async def maybe_update_personality(self, user_id: str, llm_client) -> bool:
        """检查并可能更新用户人格因子。

        返回:
            是否执行了更新
        """
        if not await self.should_update_personality(user_id):
            return False

        factors = await self.analyze_personality_with_llm(user_id, llm_client)
        if factors:
            await self.update_personality(user_id, factors)
            return True
        return False

    # ================= 长期记忆 LTM (P1.3) =================

    async def extract_ltm_from_stm(self, user_id: str, llm_client=None) -> list:
        """从 STM 中提取重要事件到 LTM。

        参数:
            user_id: 用户 ID
            llm_client: 可选的 LLM 客户端（用于智能提取）

        返回:
            提取的 LTM 条目列表
        """
        state = await self.get_user_state(user_id)
        stm = state.short_term_memory

        if len(stm) < 5:
            return []

        # 初始化 LTM 列表（如果不存在）
        if not hasattr(state, 'long_term_memory') or state.long_term_memory is None:
            state.long_term_memory = []

        extracted = []

        # 规则提取：查找重要模式
        for msg in stm:
            if msg.role != "user":
                continue

            text = msg.text
            importance = self._calculate_message_importance(text, msg.meta)

            if importance >= 0.7:
                ltm_entry = {
                    "type": "event",
                    "text": text[:200],  # 限制长度
                    "ts": msg.ts,
                    "importance": importance,
                    "meta": msg.meta,
                }

                # 去重检查
                if not self._is_duplicate_ltm(state.long_term_memory, ltm_entry):
                    state.long_term_memory.append(ltm_entry)
                    extracted.append(ltm_entry)

        # 保持 LTM 大小限制
        max_ltm = 50
        if len(state.long_term_memory) > max_ltm:
            # 按重要性和时间排序，保留最重要的
            state.long_term_memory.sort(key=lambda x: (x.get("importance", 0), x.get("ts", 0)), reverse=True)
            state.long_term_memory = state.long_term_memory[:max_ltm]

        if extracted:
            await self.save_user_state(user_id)
            logger.info("用户 %s 提取长期记忆：%s 条", user_id, len(extracted))

        return extracted

    def _calculate_message_importance(self, text: str, meta: dict) -> float:
        """计算消息的重要性分数（0-1）。"""
        importance = 0.3  # 基础分

        # 长度因素
        if len(text) > 50:
            importance += 0.1
        if len(text) > 100:
            importance += 0.1

        # 关键词检测
        important_keywords = [
            "生日", "名字", "叫我", "住在", "工作", "学校", "喜欢", "讨厌",
            "重要", "记住", "别忘了", "告诉你", "秘密", "只有你知道",
            "我是", "我的", "我们", "永远", "最",
        ]
        for kw in important_keywords:
            if kw in text:
                importance += 0.1

        # 情绪强度
        emotion = meta.get("emotion", "neutral")
        if emotion in ("happy", "sad", "angry") and meta.get("intensity", 0) > 0.7:
            importance += 0.15

        # 自述相关
        if "trigger" in meta and meta["trigger"] in ("mentioned_text", "random_chitchat"):
            importance += 0.05

        return min(1.0, importance)

    def _is_duplicate_ltm(self, ltm_list: list, new_entry: dict) -> bool:
        """检查 LTM 是否重复。"""
        new_text = new_entry.get("text", "")
        for entry in ltm_list:
            if entry.get("text", "") == new_text:
                return True
            # 相似度检查（简单版本）
            if len(new_text) > 10 and new_text[:20] == entry.get("text", "")[:20]:
                return True
        return False

    async def get_ltm(self, user_id: str) -> list:
        """获取用户长期记忆。"""
        state = await self.get_user_state(user_id)
        if hasattr(state, 'long_term_memory') and state.long_term_memory:
            return state.long_term_memory
        return []
