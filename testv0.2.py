
"""兼容入口：保留旧文件名，内部调用模块化版本。

新入口：python .\BOT\run_bot.py
配置说明：见 .\BOT\config\README.md
"""

from __future__ import annotations

from run_bot import main



if __name__ == "__main__":
    main()