# 配置说明

本项目使用 JSON 配置文件（可直接在配置里维护 key 与行为参数）。

## 文件列表

- `bot_settings.json`：主配置（由 `bot_settings.example.json` 复制）
- `group_settings.json`：群级覆盖配置（由运行时命令自动生成）

## 使用方式

1. 复制模板：

```bash
cp config/bot_settings.example.json config/bot_settings.json
```

2. 修改 `bot_settings.json`。

3. 启动：

```bash
python run_bot.py
```

## 关键字段

### `bot_settings.json`

- `random_reply_chance`：全局随机闲聊概率分母（越小越容易触发）
- `enable_memory`：全局记忆模块开关
- `admin_user_ids`：管理员 QQ 白名单（用于运行时命令鉴权）

### `group_settings.json`

结构示例见 `group_settings.example.json`，常用字段：

- `random_reply_chance`
- `enable_memory`
- `enable_image`

其中：

- `private` 表示私聊默认覆盖项
- 具体群号（字符串）表示该群覆盖项

## 管理员命令（群聊）

- `设置随机率=数字`（`0` 为关闭随机闲聊）
- `开关记忆=开/关`
- `查看运行状态`

## 注意事项

1. 群级配置会持久化到 `group_settings.json`，重启仍保留。
2. 若全局 `enable_memory=false`，即使群里设置“开关记忆=开”，记忆模块也无法启用（因为底层未初始化）。
3. 布尔值建议使用 JSON 原生 `true/false`。
