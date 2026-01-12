"""智谱视觉模型最小 demo（独立测试用）。

说明：
- 这是单独跑的测试脚本，不参与机器人主流程。
- 如果要在机器人里用视觉能力，请看 shasha_bot/ai/zhipu_vision.py。
"""

from zai import ZhipuAiClient

client = ZhipuAiClient(api_key="5d4df470843d473c91cd39b86a7e891e.7aLU3PH4OjQECx4T")  # 填写您自己的 APIKey

response = client.chat.completions.create(
    model="glm-4.6v",  # 或使用 glm-4v-flash（免费）
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "https://multimedia.nt.qq.com.cn/download?appid=1406&fileid=EhS1mwkdtuVEDIE2hvMLaiauKwEgNhiZkwwg_goouqf9r_LkkQMyBHByb2RaECqAn5OKxXNcUeRXlW5jhMl6An1sggECbmo&rkey=CAESMMGoBE1iTApkKODereO7nEOa6ATpOOqnvEWaI1VS9502cEKn4amhy2LZT3f4JdBGxw"}},
                {"type": "text", "text": "请描述这个图片"}
            ]
        }
    ]
)
print(response.choices[0].message.content)