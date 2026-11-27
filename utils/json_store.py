# utils/json_store.py
"""
Безопасное чтение JSON-файлов данных.

Если файл повреждён (обрезан, битая кодировка, BOM), приложение не должно
падать и не должно молча терять данные: сохраняем копию рядом с оригиналом
(*.broken-ДАТА.bak) и возвращаем значение по умолчанию.

Чистая логика, без PyQt — тестируется отдельно.
"""
import json
import os
import shutil
from datetime import datetime
from typing import Any

from utils.logger import log

DEFAULT_BACKUP_SUFFIX = "broken"


def backup_broken_file(path: str, suffix: str = DEFAULT_BACKUP_SUFFIX) -> str:
    """Копирует повреждённый файл рядом. Возвращает путь копии или ''."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{path}.{suffix}-{stamp}.bak"
    try:
        shutil.copy2(path, backup)
        return backup
    except OSError as e:
        log.warning(f"json_store: не удалось сохранить копию {path}: {e}")
        return ""


def load_json(
    path: str,
    default: Any = None,
    *,
    backup_broken: bool = True,
) -> Any:
    """Читает JSON; при ошибке возвращает default, а битый файл копирует в .bak."""
    if default is None:
        default = {}

    if not os.path.isfile(path):
        return default

    try:
        # utf-8-sig: файлы могли сохранить в Блокноте, тогда в начале BOM
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        backup = backup_broken_file(path) if backup_broken else ""
        name = os.path.basename(path)
        if backup:
            log.error(f"{name} повреждён ({e}); копия сохранена: {backup}")
        else:
            log.error(f"{name} повреждён ({e})")
        return default
