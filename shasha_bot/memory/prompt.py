"""Prompt 拼装模块。

职责：
- 将用户记忆、情绪、关系等信息组装成系统上下文
- 生成行为指导而非直述结论
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import (
    UserMemoryState,
    RelationState,
    BotEmotionState,
    UserEmotion,
    STMMessage,
)


def build_system_context(
    user_state: UserMemoryState,
    relation: RelationState,
    user_emotion: UserEmotion,
    bot_vad: BotEmotionState,
    base_system_prompt: str = "",
) -> str:
    """构建完整的系统提示词。

    参数:
        user_state: 用户记忆状态
        relation: 用户关系状态
        user_emotion: 当前用户情绪
        bot_vad: 机器人当前情绪
        base_system_prompt: 基础人设提示词

    返回:
        完整的系统提示词
    """
    parts = []

    # 1. 基础人设
    if base_system_prompt:
        parts.append(base_system_prompt)

    # 2. 用户信息
    user_info = _build_user_info(user_state, relation)
    if user_info:
        parts.append(f"\n【当前对话对象】\n{user_info}")

    # 3. 长期记忆（重要事件）
    ltm_info = _build_ltm_info(user_state)
    if ltm_info:
        parts.append(f"\n【你记住的重要事情】\n{ltm_info}")

    # 4. 行为指导（基于情绪和关系）
    behavior_guide = _build_behavior_guide(user_emotion, bot_vad, relation)
    if behavior_guide:
        parts.append(f"\n【本轮行为指导】\n{behavior_guide}")

    return "\n".join(parts)


def _build_ltm_info(user_state: UserMemoryState) -> str:
    """构建长期记忆信息部分。"""
    ltm = getattr(user_state, 'long_term_memory', [])
    if not ltm:
        return ""
    
    # 按重要性排序，取前5条
    sorted_ltm = sorted(ltm, key=lambda x: x.get("importance", 0), reverse=True)[:5]
    
    lines = []
    for entry in sorted_ltm:
        text = entry.get("text", "")[:100]  # 限制长度
        lines.append(f"- {text}")
    
    return "\n".join(lines)


def _build_user_info(
    user_state: UserMemoryState,
    relation: RelationState,
) -> str:
    """构建用户信息部分。"""
    lines = []

    # 昵称
    nickname = user_state.profile.nickname
    if nickname:
        lines.append(f"- 称呼: {nickname}")

    # 自述（取最近几条）
    descs = user_state.profile.self_descriptions[-3:]
    if descs:
        desc_text = "; ".join(descs)
        lines.append(f"- 自我介绍: {desc_text}")

    # 人格概述（转为自然语言）
    personality = user_state.personality
    personality_desc = _personality_to_desc(personality)
    if personality_desc:
        lines.append(f"- 性格特点: {personality_desc}")

    # 关系
    rel_desc = _relation_to_desc(relation)
    if rel_desc:
        lines.append(f"- 与你的关系: {rel_desc}")

    return "\n".join(lines)


def _personality_to_desc(personality) -> str:
    """将人格因子转为自然语言描述。"""
    traits = []

    if personality.talkative > 0.7:
        traits.append("话多")
    elif personality.talkative < 0.3:
        traits.append("沉默寡言")

    if personality.optimism > 0.7:
        traits.append("乐观开朗")
    elif personality.optimism < 0.3:
        traits.append("有些悲观")

    if personality.stability > 0.7:
        traits.append("情绪稳定")
    elif personality.stability < 0.3:
        traits.append("情绪起伏较大")

    if personality.politeness > 0.7:
        traits.append("很有礼貌")
    elif personality.politeness < 0.3:
        traits.append("说话比较直接")

    if not traits:
        return ""
    return "、".join(traits)


def _relation_to_desc(relation: RelationState) -> str:
    """将关系状态转为自然语言描述。"""
    fam = relation.familiarity
    trust = relation.trust

    if fam > 0.7:
        fam_desc = "非常熟悉的朋友"
    elif fam > 0.4:
        fam_desc = "比较熟悉"
    elif fam > 0.2:
        fam_desc = "有过几次交流"
    else:
        fam_desc = "初次接触"

    if trust > 0.7:
        trust_desc = "高度信任"
    elif trust > 0.4:
        trust_desc = "信任度一般"
    else:
        trust_desc = "信任度较低"

    return f"{fam_desc}，{trust_desc}"


def _build_behavior_guide(
    user_emotion: UserEmotion,
    bot_vad: BotEmotionState,
    relation: RelationState,
) -> str:
    """构建行为指导（基于情绪和关系）。"""
    guides = []

    # 根据用户情绪给出指导
    emo_guide = _emotion_to_guide(user_emotion)
    if emo_guide:
        guides.append(emo_guide)

    # 根据机器人情绪调整
    tone = bot_vad.get_suggested_tone()
    guides.append(f"当前语气倾向: {tone}")

    # 根据熟悉度调整
    if relation.familiarity > 0.6:
        guides.append("可以更加随意自然，使用亲昵的称呼")
    elif relation.familiarity < 0.2:
        guides.append("保持适度礼貌，不要过于亲密")

    return "; ".join(guides)


def _emotion_to_guide(emotion: UserEmotion) -> str:
    """根据用户情绪生成行为指导。"""
    label = emotion.label
    intensity = emotion.intensity

    guides = {
        "happy": "对方心情不错，可以积极互动",
        "sad": "对方似乎有些低落，语气温和一些，多一点共情",
        "angry": "对方情绪激动，保持冷静，不要火上浇油",
        "fear": "对方可能有些担忧，给予安慰和支持",
        "disgust": "对方可能对某事不满，注意倾听",
        "surprise": "对方感到意外，可以配合表达惊讶",
        "calm": "对方很平静，正常交流即可",
        "neutral": "",
    }

    base_guide = guides.get(label, "")
    if not base_guide:
        return ""

    # 根据强度调整
    if intensity > 0.7:
        return f"{base_guide}（情绪较强烈）"
    elif intensity > 0.4:
        return base_guide
    else:
        return f"{base_guide}（轻微）"


def build_chat_messages(
    stm: List[STMMessage],
    current_question: str,
    system_prompt: str,
    max_history: int = 10,
) -> List[Dict[str, str]]:
    """构建发送给 LLM 的消息列表。

    参数:
        stm: 短期记忆
        current_question: 当前用户问题
        system_prompt: 系统提示词
        max_history: 最大历史消息数

    返回:
        OpenAI 格式的消息列表
    """
    messages = [{"role": "system", "content": system_prompt}]

    # 添加历史消息
    history = stm[-max_history:] if len(stm) > max_history else stm
    for msg in history:
        role = "user" if msg.role == "user" else "assistant"
        messages.append({"role": role, "content": msg.text})

    # 添加当前问题（如果不在历史中）
    if not stm or stm[-1].text != current_question:
        messages.append({"role": "user", "content": current_question})

    return messages


def format_memory_summary(summary: Dict) -> str:
    """格式化记忆摘要为可读文本。"""
    lines = [
        f"📋 记忆摘要",
        f"用户ID: {summary.get('user_id', '未知')}",
        f"昵称: {summary.get('nickname', '未设置') or '未设置'}",
    ]

    descs = summary.get("self_descriptions", [])
    if descs:
        lines.append(f"自述: {'; '.join(descs)}")

    personality = summary.get("personality", {})
    if personality:
        lines.append(f"性格: 话多{personality.get('talkative', 0.5):.1f} / "
                    f"乐观{personality.get('optimism', 0.5):.1f} / "
                    f"稳定{personality.get('stability', 0.5):.1f}")

    relation = summary.get("relation", {})
    lines.append(f"熟悉度: {relation.get('familiarity', 0):.2f}")
    lines.append(f"信任度: {relation.get('trust', 0.5):.2f}")
    lines.append(f"对话轮数: {summary.get('stm_length', 0)}")
    lines.append(f"总消息数: {summary.get('total_msgs', 0)}")

    return "\n".join(lines)
