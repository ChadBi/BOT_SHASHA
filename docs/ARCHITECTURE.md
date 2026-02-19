# 鲨鲨 Bot 架构文档

## 1. 项目概述

**鲨鲨 (Shasha)** 是一个基于 NapCat/OneBot 协议的 QQ 机器人，使用 WebSocket 与 NapCat 服务端通信。核心特性包括：

- **多模态对话**: 文本对话、图片识别、图片编辑
- **记忆系统**: 短期记忆 (STM)、长期记忆 (LTM)、用户自述、人格分析
- **情绪系统**: VAD 情绪模型、用户情绪识别、情绪影响回复风格
- **关系系统**: 熟悉度、信任度动态变化

---

## 2. 目录结构

```
BOT_SHASHA/
├── run_bot.py               # 启动入口
├── requirements.txt         # 依赖
├── config/
│   ├── bot_settings.example.json  # 配置示例
│   └── README.md        # 配置说明
├── shasha_bot/          # 核心代码
│   ├── server.py        # WebSocket Server
│   ├── handler.py       # 消息处理主循环
│   ├── router.py        # 命令路由与上下文
│   ├── commands.py      # 命令装配（优先级）
│   ├── commands_custom.py  # 自定义命令（用户扩展点）
│   ├── settings.py      # 配置加载
│   ├── cq.py            # CQ 码解析/清洗
│   ├── ai/              # AI 服务封装
│   │   ├── __init__.py
│   │   ├── deepseek.py      # DeepSeek 文本对话
│   │   ├── zhipu_vision.py  # 智谱 GLM 图片识别
│   │   ├── aliyun_edit.py   # 阿里云 DashScope 图片编辑
│   │   └── siliconflow.py   # SiliconFlow 情绪识别 LLM
│   └── memory/          # 记忆与情绪系统
│       ├── __init__.py
│       ├── models.py        # 数据模型 ( dataclass )
│       ├── emotion.py       # 情绪识别与更新
│       ├── manager.py       # 记忆管理器
│       ├── storage.py       # 持久化存储 (JSON)
│       └── prompt.py        # Prompt 拼装工具
└── docs/                # 文档 (本文件)
```

---

## 3. 核心功能模块

### 3.1 消息处理流程

```
WebSocket 消息
    ↓
handler.py: handle_message()
    ↓
BotContext.from_event()  ← 解析事件、CQ码、@、图片等
    ↓
dispatch()  ← 按优先级匹配命令
    ↓
执行匹配的命令
```

### 3.2 功能清单

| 功能 | 触发方式 | 优先级 | 是否需要 @ |
|------|----------|--------|------------|
| 回复消息回调 | 收到 get_msg 响应 | 0 (最高) | - |
| 自定义命令 | commands_custom.py | 1 | 看具体定义 |
| @机器人+图片 | `is_mentioned && img_url` | 2 | ✅ |
| @机器人+回复 | `is_mentioned && reply_id` | 3 | ✅ |
| @机器人+文本 | `is_mentioned && 纯文本` | 4 | ✅ |
| 随机闲聊 | 随机触发、无@ | 5 | ❌ |

### 3.3 内置命令

| 命令 | 用法 | 说明 |
|------|------|------|
| 每日一图 | `每日一图` | 获取 Bing 每日壁纸 + AI 解说 |
| 菜单 | `菜单` | 查看帮助菜单 |
| 昵称=xxx | `@鲨鲨 昵称=xxx` | 设置用户昵称 |
| 自述=xxx | `@鲨鲨 自述=xxx` | 添加用户自述 |
| 查看记忆 | `@鲨鲨 查看记忆` | 查看记忆摘要 |
| 查看情感 | `@鲨鲨 查看情感` | 查看机器人当前情绪 |
| 清除自述 | `@鲨鲨 清除自述` | 清除所有自述 |
| 清除记忆 | `@鲨鲨 清除记忆` | 清除 STM + 自述 |

### 3.4 AI 服务

| 服务 | 用途 | 模型 | 配置 key |
|------|------|------|----------|
| DeepSeek | 文本对话 | `deepseek-chat` | `deepseek_api_key` |
| 智谱 GLM | 图片评价 | `glm-4.6v` | `zhipu_api_key` |
| 阿里云 DashScope | 图片编辑 | `qwen-image-edit-plus` | `aliyun_api_key` |
| SiliconFlow | 情绪识别 | `Qwen/Qwen2.5-7B-Instruct` | `siliconflow_api_key` |

### 3.5 记忆系统

```
┌─────────────────────────────────────────┐
│           UserMemoryState                │
├─────────────────────────────────────────┤
│  user_id: str                           │
│  profile: UserProfile                   │
│    ├─ nickname: str                     │
│    └─ self_descriptions: List[str]      │
│  personality: PersonalityFactors        │
│    ├─ talkative: float (0~1)            │
│    ├─ optimism: float (0~1)             │
│    ├─ stability: float (0~1)            │
│    └─ politeness: float (0~1)           │
│  short_term_memory: List[STMMessage]    │
│  long_term_memory: List[Dict]           │
│  counters: UserCounters                 │
└─────────────────────────────────────────┘
```

### 3.6 情绪系统

**BotEmotionState (VAD 模型)**:
- **V (Valence)**: 效价，-1（消极）~ +1（积极）
- **A (Arousal)**: 唤醒度，0（平静）~ 1（激动）
- **D (Dominance)**: 支配度，0（顺从）~ 1（支配）

**RelationState**:
- **familiarity**: 熟悉度 0~1（交互递增）
- **trust**: 信任度 0~1（正面情绪递增，负面情绪递减）

---

## 4. 现有架构问题

### 4.1 循环引用与硬编码

```
handler.py
    ├─ imports ai/*, memory/*, router, commands
    ↓
router.py
    ├─ imports memory.prompt (build_system_context, build_chat_messages)
    ↓
router 内的 run_* 函数
    ├─ 直接调用 memory 模块方法
    └─ 代码分散在三个文件
```

**问题**: `router.py` 承载了太多职责——既是路由框架，又是业务逻辑实现。建议拆分。

### 4.2 配置重复

```python
# settings.py
@dataclass
class BotSettings:
    stm_max_turns: int = 20
    emotion_decay_alpha: float = 0.7
    ...


# memory/manager.py
class MemoryConfig:
    STM_MAX_TURNS: int = 20
    EMOTION_DECAY_ALPHA: float = 0.7
    ...
```

**问题**: 两个配置类重复定义同名字段，`handler.py` 负责做映射。建议统一。

### 4.3 硬编码的服务初始化位置

```python
# handler.py:34-48
memory_manager = MemoryManager(config=memory_config)
if settings.siliconflow_api_key:
    emotion_client = SiliconFlowEmotionClient(...)
    memory_manager.emotion_recognizer.set_llm_client(...)
```

**问题**: 服务初始化逻辑硬编码在 handler，若新增服务需要改 handler。

### 4.4 CQ 码处理的局限

```python
# cq.py
_CQ_IMAGE_URL_RE = re.compile(r"\[CQ:image,.*?url=(http[^,\]]+)")
```

**问题**:
- 只提取了 http 开头的 URL，若有 `https` 或 base64 格式会漏
- 没有处理多种图片格式（showimg、file 等）

### 4.5 缺少统一日志

项目中使用 `print()` 而非 `logger`，不利于生产环境排查。

### 4.6 项目结构扁平

```
shasha_bot/
    ├─ server.py
    ├─ handler.py      ← 业务逻辑入口
    ├─ router.py       ← 路由+业务实现（过重）
    ├─ commands.py
    ├─ commands_custom.py
    ├─ settings.py
    ├─ cq.py
    ├─ ai/
    └─ memory/
```

**建议**: 将 `router.py` 拆分，让 handler 只做调度，业务逻辑下沉到 services。

---

## 5. 推荐的重构方案

### 5.1 拆分 router.py

```
shasha_bot/
    ├─ router.py       ← 只保留 Command 协议 + 匹配逻辑
    ├─ handlers/       ← 新增：业务处理器目录
    │   ├─ __init__.py
    │   ├─ text.py     ← 纯文本处理
    │   ├─ image.py    ← 图片相关处理
    │   ├─ reply.py    ← 回复消息处理
    │   └─ chitchat.py ← 随机闲聊处理
    └─ commands.py     ← 只做命令列表组装
```

### 5.2 统一配置

```python
# settings.py
@dataclass
class MemorySettings:
    stm_max_turns: int = 20
    emotion_decay_alpha: float = 0.7
    # ... 其他记忆相关配置

@dataclass
class BotSettings:
    # 服务配置
    host: str = "127.0.0.1"
    port: int = 8095

    # AI 配置
    deepseek_api_key: str = ...
    zhipu_api_key: str = ...
    aliyun_api_key: str = ...
    siliconflow_api_key: str = ...

    # 记忆 (使用 MemoryConfig 字段但统一命名)
    memory: MemorySettings = field(default_factory=MemorySettings)

    # 行为配置
    random_reply_chance: int = 200
    temperature: float = 1.3
```

### 5.3 引入依赖注入/服务容器

```python
# services.py
class BotServices:
    def __init__(self, settings: BotSettings):
        self.deepseek = DeepSeekText(...)
        self.vision = ZhipuVision(...)
        self.image_edit = AliyunImageEdit(...)
        self.memory = MemoryManager(...) if settings.enable_memory else None
```

### 5.4 统一日志

```python
# logging.py (新增)
import logging

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
```

### 5.5 CQ 码处理增强

```python
# cq.py
def extract_image_urls(message: str) -> List[str]:
    """提取所有图片 URL。"""
    urls = []
    for match in _CQ_IMAGE_URL_RE.finditer(message or ""):
        url = match.group(1).replace("&amp;", "&")
        urls.append(url)
    return urls
```

---

## 6. 下一步开发建议

### 6.1 短期（低风险）

1. **统一日志**: 将 `print()` 替换为 `logging`
2. **完善 CQ 码处理**: 支持 https/base64 格式、多图
3. **拆分 router.py**: 将业务实现移至 handlers/ 目录

### 6.2 中期（需规划）

1. **服务容器化**: 引入 BotServices 统一管理依赖
2. **配置统一**: 合并 MemoryConfig 与 BotSettings
3. **单元测试**: 为 router、memory 模块添加测试

### 6.3 长期（架构升级）

1. **插件系统**: 基于 setuptools entry_points 的动态插件加载
2. **事件总线**: 将 dispatch 改为事件发布订阅模式
3. **存储升级**: 考虑 SQLite 替代 JSON 文件（性能提升）

---

## 7. 快速参考

### 7.1 添加新命令

**方法 1**: 在 `commands_custom.py` 添加

```python
from .router import exact_match, prefix

async def _my_command(ctx):
    await ctx.send_text("Hello!", quote=True)

CUSTOM_COMMANDS = [
    exact_match("my_cmd", "hello", _my_command),
    prefix("echo", "echo=", lambda ctx: ctx.send_text(ctx.text[3:])),
]
```

**方法 2**: 直接修改 `commands.py` 的 `build_commands()`

### 7.2 添加新 AI 服务

1. 在 `shasha_bot/ai/` 下创建新文件
2. 实现统一接口（参考 `deepseek.py`）
3. 在 `shasha_bot/ai/__init__.py` 导出
4. 在 `handler.py` 初始化并注入 `Services`

### 7.3 配置说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `host` | str | `127.0.0.1` | WebSocket 服务地址 |
| `port` | int | `8095` | WebSocket 服务端口 |
| `system_prompt` | str | (傲娇二次元) | 机器人人设 |
| `vision_prompt` | str | (摄影师) | 图片评价 Prompt |
| `deepseek_api_key` | str | `` | DeepSeek API Key |
| `zhipu_api_key` | str | `` | 智谱 API Key |
| `aliyun_api_key` | str | `` | 阿里云 DashScope Key |
| `siliconflow_api_key` | str | `` | SiliconFlow Key (情绪识别) |
| `random_reply_chance` | int | `200` | 随机闲聊概率 1/200 |
| `temperature` | float | `1.3` | LLM 温度 |
| `enable_memory` | bool | `True` | 是否启用记忆模块 |

---

## 8. 附录

### 8.1 外部依赖版本

```txt
httpx==0.28.1      # HTTP 客户端
openai==2.14.0     # OpenAI 兼容接口
websockets==15.0.1 # WebSocket 服务
zai-sdk            # 智谱 SDK
dashscope          # 阿里云 SDK
```

### 8.2 OneBot 协议参考

本项目实现 OneBot v11/WebSocket 协议：
- 接收: `post_type=message` 事件
- 发送: `send_msg`、`get_msg` API

参考: [OneBot 文档](https://github.com/botuniverse/onebot-11)

---

> 文档版本: 2026-02-19
> 维护者: Claude Code
