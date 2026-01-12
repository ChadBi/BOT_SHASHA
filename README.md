# BOT 目录说明

这份文档是给“只关心 BOT 目录”的快速索引；更完整的工程文档在根目录：
- [README.md](../README.md)

## 入口

- [run_bot.py](run_bot.py)：启动 WebSocket Server

## 配置

- [config/bot_settings.json](config/bot_settings.json)：主配置（硬编码 key）
- [config/README.md](config/README.md)：配置说明

## 核心包

- [shasha_bot](shasha_bot)：机器人核心
  - [shasha_bot/handler.py](shasha_bot/handler.py)：主消息循环
  - [shasha_bot/router.py](shasha_bot/router.py)：路由/上下文/命令工具
  - [shasha_bot/commands.py](shasha_bot/commands.py)：命令装配与优先级
  - [shasha_bot/commands_custom.py](shasha_bot/commands_custom.py)：自定义命令入口
  - [shasha_bot/ai](shasha_bot/ai)：AI 调用封装
