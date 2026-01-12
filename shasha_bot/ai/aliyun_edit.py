"""阿里云 DashScope 图片编辑封装。

流程：
1) 下载图片到本地临时文件
2) 转成 file:// 形式传给 dashscope SDK（解决外网图片不可访问/鉴权问题）
3) 调用 qwen-image-edit-plus
4) 解析返回图片 url，并包装成 CQ:image
5) 清理临时文件
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
import uuid

import httpx


@dataclass
class AliyunImageEdit:
    """图片编辑（修图/风格化等）。"""
    api_key: str

    async def edit(self, image_url: str, prompt: str) -> str:
        """编辑图片并返回 CQ:image（或错误信息文本）。"""
        if not self.api_key or "YOUR_ALIYUN_API_KEY" in self.api_key:
            return "未配置 ALIYUN_API_KEY (请在配置中填入阿里云 DashScope Key)"

        try:
            import dashscope
            from dashscope import MultiModalConversation
        except Exception as e:
            return f"未安装 dashscope，无法修图: {e}"

        # DashScope 全局设置 api_key
        dashscope.api_key = self.api_key

        local_image_path: str | None = None
        image_input: str | None = None

        try:
            # 先把 QQ/外链图片下载到本地，保证 SDK 可读
            print(f"📥 正在下载图片: {image_url}")
            async with httpx.AsyncClient() as client:
                resp = await client.get(image_url, timeout=30.0)
                if resp.status_code != 200:
                    return f"下载图片失败: {resp.status_code}"

                # 临时目录放在 shasha_bot/temp_images（不进 git 也可手动清理）
                temp_dir = Path(__file__).resolve().parent.parent / "temp_images"
                temp_dir.mkdir(parents=True, exist_ok=True)

                file_name = f"{uuid.uuid4()}.jpg"
                local_image_path = str(temp_dir / file_name)
                Path(local_image_path).write_bytes(resp.content)

                # Windows 路径转成 file:// URL
                abs_path = os.path.abspath(local_image_path).replace("\\", "/")
                image_input = f"file://{abs_path}"
                print(f"💾 图片已保存至: {image_input}")

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": image_input},
                        {"text": prompt},
                    ],
                }
            ]

            print(f"🎨 正在调用阿里云修图 (SDK): {prompt}")

            def _call_sdk():
                return MultiModalConversation.call(
                    model="qwen-image-edit-plus",
                    messages=messages,
                )

            response = await asyncio.to_thread(_call_sdk)

            if response.status_code == 200:
                try:
                    if response.output and response.output.choices:
                        content_list = response.output.choices[0].message.content
                        for item in content_list:
                            if "image" in item:
                                result_image_url = item["image"]
                                return f"[CQ:image,file={result_image_url}]"
                        return "修图成功，但未找到返回的图片链接。"
                    return "修图成功，但返回数据为空。"
                except Exception as e:
                    return f"修图失败: 解析响应出错 ({e})"

            error_msg = getattr(response, "message", "Unknown error")
            code = getattr(response, "code", "Unknown code")
            print(f"❌ 阿里云 API 报错: {code} - {error_msg}")
            return f"修图失败: {error_msg}"

        except Exception as e:
            print(f"❌ 调用阿里云出错: {e}")
            return f"修图请求发送失败: {e}"
        finally:
            # 无论成功失败都尽量清理临时文件
            if local_image_path and os.path.exists(local_image_path):
                try:
                    os.remove(local_image_path)
                    print("🧹 临时图片已清理")
                except Exception:
                    pass
