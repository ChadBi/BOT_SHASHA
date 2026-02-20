# BOT 目录说明

这是鲨鲨机器人的运行目录说明，聚焦 **如何启动 / 如何配置 / 如何运维**。

## 快速开始

### 1) 准备配置

1. 复制主配置模板：

```bash
cp config/bot_settings.example.json config/bot_settings.json
```

2. 在 `config/bot_settings.json` 填写你的 API Key（DeepSeek / 智谱 / 阿里云等）。

3. 可选：配置管理员白名单 `admin_user_ids`，用于运行时管理命令。

### 2) 启动

```bash
python run_bot.py
```

默认 WebSocket 地址：`ws://127.0.0.1:8095`

## 配置文件说明

- 主配置：`config/bot_settings.json`
- 配置文档：`config/README.md`
- 群级配置示例：`config/group_settings.example.json`
- 群级运行时配置文件：`config/group_settings.json`（首次使用管理员命令后自动生成）

## 群级行为覆盖（新增）

现在支持按群覆盖以下行为：

- 随机闲聊触发率（`random_reply_chance`）
- 记忆功能开关（`enable_memory`）
- 图片能力开关（`enable_image`）

> 说明：群级配置会持久化到 `config/group_settings.json`，重启后仍然生效。

## 管理员运行时命令（群聊中使用）

以下命令仅 `admin_user_ids` 白名单用户可用：

- `设置随机率=数字`
  - 例如：`设置随机率=100`
  - `0` 表示关闭随机闲聊
- `开关记忆=开/关`
  - 例如：`开关记忆=关`
- `查看运行状态`
  - 查看当前群随机率/记忆开关/图片开关

## 功能索引

- `shasha_bot/handler.py`：主消息循环与服务初始化
- `shasha_bot/router.py`：路由、上下文、核心处理逻辑
- `shasha_bot/commands.py`：命令装配与优先级
- `shasha_bot/commands_custom.py`：自定义命令（含管理员命令）
- `shasha_bot/group_config.py`：群级配置读取、缓存、持久化
- `shasha_bot/ai/`：AI 客户端封装
- `shasha_bot/memory/`：记忆模块

## 常见问题

### Q1：为什么我配置了 `开关记忆=开` 但仍提示未启用？

请确认主配置 `bot_settings.json` 中 `enable_memory` 为 `true`。如果全局关闭，记忆管理器不会初始化，群级开关无法单独启用。

### Q2：管理员命令没反应？

请确认：

1. 在群聊中发送（不是私聊）
2. 发送者 QQ 在 `admin_user_ids` 中
3. 命令格式正确（包含 `=`）
