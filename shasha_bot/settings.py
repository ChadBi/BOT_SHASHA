"""配置模块。

你只需要关心：BOT/config/bot_settings.json。
本模块负责把 JSON 读出来并转换成 BotSettings（带默认值/类型转换）。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class BotSettings:
    """机器人运行时配置（从 JSON 加载）。"""

    # WebSocket server（NapCat 会连到这里）
    host: str = "127.0.0.1"
    port: int = 8095

    # Prompts（人设/看图风格）
    system_prompt: str = "你是一个傲娇的二次元美少女机器人，说话要带一点颜文字，名字叫'鲨鲨'。"
    vision_prompt: str = (
        "你是一个比较专业的摄影师，请简短评价下面的图片内容，不要超过50个字,一般情况下20字左右。"
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
    stm_max_turns: int = 20  # 短期记忆最大轮数
    personality_update_min_msgs: int = 50  # 触发人格总结的最小消息数
    personality_update_cooldown_hours: float = 24.0  # 人格总结冷却时间（小时）
    emotion_decay_alpha: float = 0.7  # 情绪衰减系数（0~1）
    max_self_descriptions: int = 10  # 最大自述条数
    enable_memory: bool = True  # 是否启用记忆模块

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
        # 所有字段都从 JSON 里取；取不到就用默认值。
        return config.get(key, default)

    host = str(pick("host", "127.0.0.1"))
    port_raw = pick("port", 8095)
    try:
        port = int(port_raw)
    except Exception:
        port = 8095

    random_reply_chance_raw = pick("random_reply_chance", 200)
    try:
        random_reply_chance = int(random_reply_chance_raw)
    except Exception:
        random_reply_chance = 200

    max_text_tokens_raw = pick("max_text_tokens", 50)
    try:
        max_text_tokens = int(max_text_tokens_raw)
    except Exception:
        max_text_tokens = 50

    temperature_raw = pick("temperature", 1.3)
    try:
        temperature = float(temperature_raw)
    except Exception:
        temperature = 1.3

    # 记忆模块配置
    stm_max_turns_raw = pick("stm_max_turns", 20)
    try:
        stm_max_turns = int(stm_max_turns_raw)
    except Exception:
        stm_max_turns = 20

    personality_update_min_msgs_raw = pick("personality_update_min_msgs", 50)
    try:
        personality_update_min_msgs = int(personality_update_min_msgs_raw)
    except Exception:
        personality_update_min_msgs = 50

    personality_update_cooldown_hours_raw = pick("personality_update_cooldown_hours", 24.0)
    try:
        personality_update_cooldown_hours = float(personality_update_cooldown_hours_raw)
    except Exception:
        personality_update_cooldown_hours = 24.0

    emotion_decay_alpha_raw = pick("emotion_decay_alpha", 0.7)
    try:
        emotion_decay_alpha = float(emotion_decay_alpha_raw)
    except Exception:
        emotion_decay_alpha = 0.7

    max_self_descriptions_raw = pick("max_self_descriptions", 10)
    try:
        max_self_descriptions = int(max_self_descriptions_raw)
    except Exception:
        max_self_descriptions = 10

    enable_memory = _to_bool(pick("enable_memory", True), True)
    enable_rate_limit = _to_bool(pick("enable_rate_limit", True), True)

    log_level = str(pick("log_level", "INFO")).upper().strip() or "INFO"

    rate_limit_window_seconds = int(pick("rate_limit_window_seconds", 10))
    rate_limit_user_max_calls = int(pick("rate_limit_user_max_calls", 6))
    rate_limit_group_max_calls = int(pick("rate_limit_group_max_calls", 30))

    api_retry_attempts = int(pick("api_retry_attempts", 2))
    api_retry_base_delay = float(pick("api_retry_base_delay", 0.4))
    circuit_breaker_fail_threshold = int(pick("circuit_breaker_fail_threshold", 3))
    circuit_breaker_cooldown_seconds = int(pick("circuit_breaker_cooldown_seconds", 30))

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
        stm_max_turns=stm_max_turns,
        personality_update_min_msgs=personality_update_min_msgs,
        personality_update_cooldown_hours=personality_update_cooldown_hours,
        emotion_decay_alpha=emotion_decay_alpha,
        max_self_descriptions=max_self_descriptions,
        enable_memory=enable_memory,
        log_level=log_level,
        enable_rate_limit=enable_rate_limit,
        rate_limit_window_seconds=rate_limit_window_seconds,
        rate_limit_user_max_calls=rate_limit_user_max_calls,
        rate_limit_group_max_calls=rate_limit_group_max_calls,
        api_retry_attempts=api_retry_attempts,
        api_retry_base_delay=api_retry_base_delay,
        circuit_breaker_fail_threshold=circuit_breaker_fail_threshold,
        circuit_breaker_cooldown_seconds=circuit_breaker_cooldown_seconds,
    )
