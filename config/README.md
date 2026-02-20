# 配置说明

本项目使用 JSON 配置文件（按你的习惯：直接在配置文件里硬编码 key）。

## 使用方式（JSON 文件）

复制 `bot_settings.example.json` 为 `bot_settings.json` 并填写 key（或直接编辑现成的 `bot_settings.json`）。

启动：

```powershell
python .\BOT\run_bot.py
```


### 布尔值说明

- 布尔字段建议使用 JSON 原生 `true/false`。
- 兼容字符串格式：`"true"`, `"false"`, `"1"`, `"0"`, `"yes"`, `"no"`（大小写不敏感）。
