"""日志配置模块。

统一配置项目日志，使用 logger 而非 print。
"""

import logging
import sys

# 日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    """初始化日志配置。

    参数:
        level: 日志级别，默认 INFO

    返回:
        已配置的根 logger
    """
    # 配置根 logger
    root = logging.getLogger()
    root.setLevel(level)

    # 控制台处理器
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    handler.setFormatter(formatter)

    # 避免重复添加处理器
    if not root.handlers:
        root.addHandler(handler)

    return root


# 便捷函数：获取模块 logger
def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger。"""
    return logging.getLogger(name)
