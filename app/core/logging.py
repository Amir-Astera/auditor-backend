import logging
import sys
from typing import Optional

LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """
    Базовая конфигурация логирования для всего приложения.

    - лог в stdout (для Docker/Kubernetes и консоли);
    - простой формат с временем, уровнем, именем логгера;
    - отключаем повторную конфигурацию, если уже настроено.
    """
    if logging.getLogger().handlers:
        # Логирование уже настроено, дублировать конфиг не будем
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Возвращает именованный логгер.
    Перед использованием нужно один раз вызвать configure_logging()
    (обычно в main.py при старте приложения).
    """
    return logging.getLogger(name)

