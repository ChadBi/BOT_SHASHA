"""配置模块。

所有配置集中在 BotSettings 中，从 config/bot_settings.json 加载。
提供嵌套的 MemorySettings 用于记忆模块配置。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class MemorySettings:
    """记忆模块配置（嵌套在 BotSettings 中）。"""
    stm_max_turns: int = 20  # 短期记忆最大轮数
    personality_update_min_msgs: int = 50  # 触发人格总结的最小消息数
    personality_update_cooldown_hours: float = 24.0  # 人格总结冷却时间（小时）
    emotion_decay_alpha: float = 0.7  # 情绪衰减系数（0~1）
    max_self_descriptions: int = 10  # 最大自述条数
    familiarity_step: float = 0.01  # 熟悉度更新步长
    trust_step: float = 0.005  # 信任度更新步长


@dataclass(frozen=True)
class BotSettings:
    """机器人运行时配置（从 JSON 加载）。"""
    host: str = "127.0.0.1"
    port: int = 8095

    # Prompts（人设/看图风格）
    system_prompt: str = "你是一个傲娇的二次元美少女机器人，说话要带一点颜文字，名字叫'鲨鲨'。"
    vision_prompt: str = (
        "你是一个比较专业的摄影师，请简短评价下面的图片内容，不要超过 50 个字，一般情况下 20 字左右。"
        "评价可以稍微抽象幽默一点，偶尔也可以批评讽刺，但不要太过分。"
    )

    # Keys / endpoints（AI 相关）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    zhipu_api_key: str = ""

    aliyun_api_key: str = ""

    siliconflow_api_key: str = ""  # SiliconFlow 情绪识别

    # Behavior（行为参数）
    random_reply_chance: int = 200
    max_text_tokens: int = 50
    temperature: float = 1.3

    # Memory（记忆模块配置）
    enable_memory: bool = True
    memory: MemorySettings = field(default_factory=MemorySettings)

    # Logging
    log_level: str = "INFO"

    # Stability / throttling
    enable_rate_limit: bool = True
    rate_limit_window_seconds: int = 10
    rate_limit_user_max_calls: int = 6
    rate_limit_group_max_calls: int = 30

    # API reliability
    api_retry_attempts: int = 2
    api_retry_base_delay: float = 0.4
    circuit_breaker_fail_threshold: int = 3
    circuit_breaker_cooldown_seconds: int = 30

    # Admin
    admin_user_ids: Tuple[int, ...] = ()


def _read_json_file(path: Path) -> dict[str, Any]:
    """读取 JSON 文件为 dict；文件不存在则返回空 dict。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _to_bool(value: Any, default: bool) -> bool:
    """把常见输入转换为布尔值。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    return default


def load_settings(config_path: Optional[str] = None) -> BotSettings:
    """加载配置：仅从 JSON 配置文件读取。"""
    config: dict[str, Any] = {}
    if config_path:
        config = _read_json_file(Path(config_path))

    def pick(key: str, default: Any) -> Any:
        return config.get(key, default)

    def pick_int(key: str, default: int) -> int:
        try:
            val = config.get(key)
            return int(val) if val is not None else default
        except Exception:
            return default

    def pick_float(key: str, default: float) -> float:
        try:
            val = config.get(key)
            return float(val) if val is not None else default
        except Exception:
            return default

    def pick_bool(key: str, default: bool) -> bool:
        try:
            return bool(config.get(key, default))
        except Exception:
            return default

    host = str(pick("host", "127.0.0.1"))
    port = pick_int("port", 8095)

    # 记忆模块配置
    stm_max_turns = pick_int("stm_max_turns", MemorySettings.stm_max_turns)
    personality_update_min_msgs = pick_int("personality_update_min_msgs", MemorySettings.personality_update_min_msgs)
    personality_update_cooldown_hours = pick_float("personality_update_cooldown_hours", MemorySettings.personality_update_cooldown_hours)
    emotion_decay_alpha = pick_float("emotion_decay_alpha", MemorySettings.emotion_decay_alpha)
    max_self_descriptions = pick_int("max_self_descriptions", MemorySettings.max_self_descriptions)
    familiarity_step = pick_float("familiarity_step", MemorySettings.familiarity_step)
    trust_step = pick_float("trust_step", MemorySettings.trust_step)

    memory = MemorySettings(
        stm_max_turns=stm_max_turns,
        personality_update_min_msgs=personality_update_min_msgs,
        personality_update_cooldown_hours=personality_update_cooldown_hours,
        emotion_decay_alpha=emotion_decay_alpha,
        max_self_descriptions=max_self_descriptions,
        familiarity_step=familiarity_step,
        trust_step=trust_step,
    )

    random_reply_chance = pick_int("random_reply_chance", 200)
    max_text_tokens = pick_int("max_text_tokens", 50)
    temperature = pick_float("temperature", 1.3)
    enable_memory = pick_bool("enable_memory", True)
    enable_rate_limit = pick_bool("enable_rate_limit", True)
    log_level = str(pick("log_level", "INFO")).upper().strip() or "INFO"
    rate_limit_window_seconds = pick_int("rate_limit_window_seconds", 10)
    rate_limit_user_max_calls = pick_int("rate_limit_user_max_calls", 6)
    rate_limit_group_max_calls = pick_int("rate_limit_group_max_calls", 30)
    api_retry_attempts = pick_int("api_retry_attempts", 2)
    api_retry_base_delay = pick_float("api_retry_base_delay", 0.4)
    circuit_breaker_fail_threshold = pick_int("circuit_breaker_fail_threshold", 3)
    circuit_breaker_cooldown_seconds = pick_int("circuit_breaker_cooldown_seconds", 30)

    admin_user_ids_raw = pick("admin_user_ids", [])
    admin_user_ids: list[int] = []
    if isinstance(admin_user_ids_raw, list):
        for uid in admin_user_ids_raw:
            try:
                admin_user_ids.append(int(uid))
            except Exception:
                continue

    return BotSettings(
        host=host,
        port=port,
        system_prompt=str(pick("system_prompt", BotSettings.system_prompt)),
        vision_prompt=str(pick("vision_prompt", BotSettings.vision_prompt)),
        deepseek_api_key=str(pick("deepseek_api_key", "")),
        deepseek_base_url=str(pick("deepseek_base_url", "https://api.deepseek.com")),
        zhipu_api_key=str(pick("zhipu_api_key", "")),
        aliyun_api_key=str(pick("aliyun_api_key", "")),
        siliconflow_api_key=str(pick("siliconflow_api_key", "")),
        random_reply_chance=random_reply_chance,
        max_text_tokens=max_text_tokens,
        temperature=temperature,
        enable_memory=enable_memory,
        memory=memory,
        log_level=log_level,
        enable_rate_limit=enable_rate_limit,
        rate_limit_window_seconds=rate_limit_window_seconds,
        rate_limit_user_max_calls=rate_limit_user_max_calls,
        rate_limit_group_max_calls=rate_limit_group_max_calls,
        api_retry_attempts=api_retry_attempts,
        api_retry_base_delay=api_retry_base_delay,
        circuit_breaker_fail_threshold=circuit_breaker_fail_threshold,
        circuit_breaker_cooldown_seconds=circuit_breaker_cooldown_seconds,
        admin_user_ids=tuple(admin_user_ids),
    )
