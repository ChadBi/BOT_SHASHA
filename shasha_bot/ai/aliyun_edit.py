"""阿里云 DashScope 图片编辑封装。"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AliyunImageEdit:
    """图片编辑（修图/风格化等）。"""

    api_key: str
    retry_attempts: int = 2
    retry_base_delay: float = 0.4

    async def edit(self, image_url: str, prompt: str) -> str:
        if not self.api_key or "YOUR_ALIYUN_API_KEY" in self.api_key:
            return "未配置 ALIYUN_API_KEY (请在配置中填入阿里云 DashScope Key)"

        try:
            import dashscope
            from dashscope import MultiModalConversation
        except Exception as e:
            return f"未安装 dashscope，无法修图：{e}"

        dashscope.api_key = self.api_key
        local_image_path: str | None = None

        try:
            # 先把 QQ/外链图片下载到本地，保证 SDK 可读
            logger.info("正在下载图片：%s", image_url)
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(image_url)
                if resp.status_code != 200:
                    return f"下载图片失败：{resp.status_code}"

                temp_dir = Path(__file__).resolve().parent.parent / "temp_images"
                temp_dir.mkdir(parents=True, exist_ok=True)
                local_image_path = str(temp_dir / f"{uuid.uuid4()}.jpg")
                Path(local_image_path).write_bytes(resp.content)

                # Windows 路径转成 file:// URL
                abs_path = os.path.abspath(local_image_path).replace("\\", "/")
                image_input = f"file://{abs_path}"
                logger.info("图片已保存至：%s", image_input)

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": image_input},
                        {"text": prompt},
                    ],
                }
            ]

            logger.info("正在调用阿里云修图 (SDK): %s", prompt)

            def _call_sdk():
                return MultiModalConversation.call(model="qwen-image-edit-plus", messages=messages)

            attempts = max(1, self.retry_attempts + 1)
            for i in range(attempts):
                try:
                    response = await asyncio.to_thread(_call_sdk)
                    if response.status_code != 200:
                        error_msg = getattr(response, "message", "Unknown error")
                        if i == attempts - 1:
                            return f"修图失败：{error_msg}"
                        await asyncio.sleep(self.retry_base_delay * (2**i))
                        continue

                    if response.output and response.output.choices:
                        for item in response.output.choices[0].message.content:
                            if "image" in item:
                                return f"[CQ:image,file={item['image']}]"
                    return "修图成功，但未找到返回的图片链接。"
                except Exception as e:
                    if i == attempts - 1:
                        logger.error("aliyun edit error after retries: %s", e)
                        return f"修图请求发送失败：{e}"
                    await asyncio.sleep(self.retry_base_delay * (2**i))

            return "修图失败，请稍后再试。"

        except Exception as e:
            logger.error("调用阿里云出错：%s", e)
            return f"修图请求发送失败：{e}"
        finally:
            if local_image_path and os.path.exists(local_image_path):
                try:
                    os.remove(local_image_path)
                except Exception:
                    logger.debug("临时图片删除失败：%s", local_image_path)
