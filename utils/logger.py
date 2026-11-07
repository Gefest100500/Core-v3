# utils/logger.py
"""
Логирование Core V3.0.

Логи пишутся в <папка программы>/Logs/core.log
- Ротация: 2 МБ × 5 файлов
- Буфер сбрасывается после каждой записи (видны в реальном времени)
- Дублирование в консоль с уровнем INFO
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


# =========================================================
# ПУТЬ К ЛОГАМ
# =========================================================
def _get_logs_dir() -> str:
    """Возвращает папку для логов строго в папке программы."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent

    path = str(base / "Logs")
    try:
        os.makedirs(path, exist_ok=True)
    except (OSError, PermissionError):
        pass
    return path


LOG_DIR = _get_logs_dir()
LOG_FILE = os.path.join(LOG_DIR, "core.log")


# =========================================================
# HANDLER С FLUSH
# =========================================================
class FlushRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler, который сбрасывает буфер после каждой записи."""

    def emit(self, record):
        super().emit(record)
        try:
            self.flush()
        except Exception:
            pass


# =========================================================
# ЛОГГЕР
# =========================================================
logger = logging.getLogger("Core")
logger.setLevel(logging.DEBUG)

# Чтобы не было дублирования handler'ов при повторном импорте
if not logger.handlers:
    try:
        handler = FlushRotatingFileHandler(
            LOG_FILE,
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
            delay=False,
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(handler)
    except (OSError, PermissionError):
        pass

    # Дублируем в консоль
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console)

    # Не пробрасывать в корневой логгер
    logger.propagate = False


log = logger