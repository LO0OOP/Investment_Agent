import logging
import sys
from typing import Optional
from src.common.config import settings


_LOGGER_CONFIGURED = False


def setup_logging( 
    level: str = settings.app["log_level"],
    fmt: Optional[str] = None,
) -> None:
    """
    Configure global logging settings.
    This function should be called ONLY ONCE.
    """
    global _LOGGER_CONFIGURED

    if _LOGGER_CONFIGURED:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt
        or "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 防止重复添加 handler
    if not root_logger.handlers:
        root_logger.addHandler(handler)

    # 控制第三方库日志噪音
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("ccxt").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    _LOGGER_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a module-level logger.
    """
    return logging.getLogger(name)
