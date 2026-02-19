"""服务容器。

统一管理 AI 服务和记忆模块的初始化与注入。
从 BotSettings 读取配置，创建并管理所有服务实例。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .settings import BotSettings, MemorySettings
from .ai import DeepSeekText, ZhipuVision, AliyunImageEdit, SiliconFlowEmotionClient
from .memory import MemoryManager

logger = logging.getLogger(__name__)


@dataclass
class BotServices:
    """服务容器。

    职责：
    - 统一管理 AI 服务实例
    - 统一管理记忆模块
    - 提供服务初始化入口

    外部通过 services 调用，示例：
    - services.deepseek.ask(text)
    - services.vision.ask(url)
    - services.memory.append_to_stm(...)
    """

    # AI 服务
    deepseek: DeepSeekText
    vision: ZhipuVision
    image_edit: AliyunImageEdit

    # 记忆模块（可选）
    memory: Optional[MemoryManager] = None

    @classmethod
    def from_settings(cls, settings: BotSettings) -> "BotServices":
        """从配置创建所有服务。

        参数:
            settings: BotSettings 实例

        返回:
            BotServices 实例
        """
        logger.info("正在初始化 AI 服务...")

        # 初始化 AI 服务
        deepseek = DeepSeekText(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            system_prompt=settings.system_prompt,
            temperature=settings.temperature,
            max_tokens=settings.max_text_tokens,
        )

        vision = ZhipuVision(
            api_key=settings.zhipu_api_key,
            system_prompt=settings.system_prompt,
            vision_prompt=settings.vision_prompt,
            temperature=settings.temperature,
        )

        image_edit = AliyunImageEdit(api_key=settings.aliyun_api_key)

        # 初始化记忆模块（如果启用）
        memory: Optional[MemoryManager] = None
        if settings.enable_memory:
            logger.info("正在初始化记忆模块...")
            memory = cls._init_memory(settings, settings.memory)

        return cls(
            deepseek=deepseek,
            vision=vision,
            image_edit=image_edit,
            memory=memory,
        )

    @classmethod
    def _init_memory(cls, settings: BotSettings, memory_config: MemorySettings) -> MemoryManager:
        """初始化记忆模块。

        参数:
            settings: BotSettings 实例
            memory_config: MemorySettings 配置

        返回:
            MemoryManager 实例
        """
        memory = MemoryManager(config=memory_config)

        # 如果配置了 SiliconFlow API key，初始化 LLM 情绪识别
        if settings.siliconflow_api_key:
            emotion_client = SiliconFlowEmotionClient(api_key=settings.siliconflow_api_key)
            memory.emotion_recognizer = emotion_client
            logger.info("[memory] 记忆模块已启用（含 LLM 情绪识别）")
        else:
            logger.info("[memory] 记忆模块已启用（规则情绪识别）")

        return memory
