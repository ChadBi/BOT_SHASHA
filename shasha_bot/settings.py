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

    # Behavior（行为参数）
    random_reply_chance: int = 200
    max_text_tokens: int = 50
    temperature: float = 1.3


def _read_json_file(path: Path) -> dict[str, Any]:
    """读取 JSON 文件为 dict；文件不存在则返回空 dict。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


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

    return BotSettings(
        host=host,
        port=port,
        system_prompt=str(pick("system_prompt", BotSettings.system_prompt)),
        vision_prompt=str(pick("vision_prompt", BotSettings.vision_prompt)),
        deepseek_api_key=str(pick("deepseek_api_key", "")),
        deepseek_base_url=str(pick("deepseek_base_url", "https://api.deepseek.com")),
        zhipu_api_key=str(pick("zhipu_api_key", "")),
        aliyun_api_key=str(pick("aliyun_api_key", "")),
        random_reply_chance=random_reply_chance,
        max_text_tokens=max_text_tokens,
        temperature=temperature,
    )
