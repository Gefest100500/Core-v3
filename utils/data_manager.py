# utils/data_manager.py
"""Менеджер данных."""
import concurrent.futures
import hashlib
import json
import os
import queue
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from utils.file_utils import get_user_data_dir, get_bundled_data_dir
from utils.logger import log

DATA_DIR = Path(get_user_data_dir())
BUNDLED_DIR = Path(get_bundled_data_dir())

BUNDLED_FILES = [
    "gm_data.json",
    "gm_ip.json",
    "standard_comments.json",
    "inventory_plans.json",
    "kv_rules.json",
    "kv_reason_schema.json",
    "unwanted.json",
    "timesheet.json",
    "gm_cities_cache.json",
    "checklists.json",
    "checklists_state.json",
    "distance_history.json",
    "steal_codes.json",
    "user_settings.json",
    "guide.json",
]

HISTORY_PATH = DATA_DIR / "actions_history.json"
INVENTORY_PATH = DATA_DIR / "active_inventory.json"
INVENTORY_ARCHIVE_PATH = DATA_DIR / "inventory_archive.json"
GM_DATA_PATH = DATA_DIR / "gm_data.json"
INVENTORY_PLANS_PATH = DATA_DIR / "inventory_plans.json"
GM_NOTES_PATH = DATA_DIR / "gm_notes.json"
STANDARD_COMMENTS_PATH = DATA_DIR / "standard_comments.json"
GUIDE_PATH = DATA_DIR / "guide.json"

EMAILS_DIR = DATA_DIR / "emails"
EMAILS_PATH = EMAILS_DIR / "emails.json"


def _ensure_bundled_files():
    """Копирует дефолтные справочники из _internal в LOCALAPPDATA при первом запуске."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for filename in BUNDLED_FILES:
        target = DATA_DIR / filename
        source = BUNDLED_DIR / filename
        if not target.exists() and source.exists():
            try:
                shutil.copy2(source, target)
                log.info(f"Скопирован дефолтный файл: {filename}")
            except Exception as e:
                log.warning(f"Не удалось скопировать {filename}: {e}")

_ensure_bundled_files()


class DataManager:
    def __init__(self):
        self._cache = {}
        self._locks = {}
        self._locks_guard = threading.Lock()
        self._closing = False

        self._write_queue = queue.Queue()

        self._read_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="DataRead"
        )

        self._writer_thread = threading.Thread(
            target=self._writer_loop, daemon=True, name="DataWriter"
        )
        self._writer_thread.start()

        self._root = None
        log.info("DataManager инициализирован")

    def set_root(self, root):
        self._root = root

    def _writer_loop(self):
        while not self._closing:
            try:
                item = self._write_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            name, path, data = item
            try:
                lock = self._get_lock(name)
                with lock:
                    self._write_file(name, path, data)
            except Exception:
                log.exception(f"Ошибка записи {name}")
            finally:
                self._write_queue.task_done()

    def _get_lock(self, name):
        with self._locks_guard:
            if name not in self._locks:
                self._locks[name] = threading.Lock()
            return self._locks[name]

    def _read_file(self, name, path, force=False):
        if self._closing:
            cached = self._cache.get(name)
            return cached[0] if cached else None
        try:
            mtime = os.path.getmtime(str(path))
        except OSError:
            mtime = None
        cached = self._cache.get(name)
        if cached is not None and not force:
            cached_data, cached_mtime = cached
            if cached_mtime == mtime:
                return cached_data
        if mtime is None:
            self._cache[name] = (None, None)
            return None
        lock = self._get_lock(name)
        with lock:
            cached = self._cache.get(name)
            if cached is not None and not force:
                cached_data, cached_mtime = cached
                if cached_mtime == mtime:
                    return cached_data
            try:
                with open(str(path), "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._cache[name] = (data, mtime)
                return data
            except json.JSONDecodeError as e:
                log.error(f"JSON повреждён ({name}): {e}")
                self._cache[name] = (None, mtime)
                return None
            except (IOError, OSError) as e:
                log.warning(f"Ошибка чтения {name}: {e}")
                cached = self._cache.get(name)
                return cached[0] if cached else None

    def _write_file(self, name, path, data):
        try:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            with open(str(tmp_path), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            last_exc = None
            for attempt in range(5):
                try:
                    os.replace(str(tmp_path), str(path))
                    last_exc = None
                    break
                except PermissionError as e:
                    last_exc = e
                    time.sleep(0.02)
            if last_exc is not None:
                raise last_exc
            try:
                mtime = os.path.getmtime(str(path))
            except OSError:
                mtime = time.time()
            self._cache[name] = (data, mtime)
        except Exception:
            log.exception(f"Ошибка записи {name}")

    def _write_async(self, name, path, data):
        self._cache[name] = (data, None)
        try:
            self._write_queue.put_nowait((name, path, data))
        except queue.Full:
            log.warning(f"Очередь записи переполнена: {name}")

    def get_history(self):
        return self._read_file("history", HISTORY_PATH) or []

    def set_history(self, history):
        new_history = list(history)[-100:]
        lock = self._get_lock("history")
        with lock:
            self._cache["history"] = (new_history, None)
        try:
            self._write_queue.put_nowait(("history", HISTORY_PATH, new_history))
        except queue.Full:
            log.warning("Очередь записи переполнена: history")
        log.info(f"История обновлена: {len(new_history)} записей")

    def add_action(self, action, details="", icon="•"):
        history = self._read_file("history", HISTORY_PATH) or []
        new_history = list(history)
        new_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
            "icon": icon,
        })
        new_history = new_history[-100:]
        lock = self._get_lock("history")
        with lock:
            self._cache["history"] = (new_history, None)
        try:
            self._write_queue.put_nowait(("history", HISTORY_PATH, new_history))
        except queue.Full:
            log.warning("Очередь записи переполнена: history")
        log.info(f"История: {action} — {details}")

    def get_active_inventory(self):
        return self._read_file("active_inventory", INVENTORY_PATH)

    def set_active_inventory(self, data):
        if data is None:
            if INVENTORY_PATH.exists():
                try:
                    os.remove(str(INVENTORY_PATH))
                except OSError:
                    log.warning("Не удалось удалить active_inventory.json")
            self._cache["active_inventory"] = (None, None)
        else:
            self._write_async("active_inventory", INVENTORY_PATH, data)

    def get_inventory_archive(self):
        return self._read_file("inventory_archive", INVENTORY_ARCHIVE_PATH) or []

    def set_inventory_archive(self, data):
        self._write_async("inventory_archive", INVENTORY_ARCHIVE_PATH, data)

    def get_inventory_plans(self):
        return self._read_file("inventory_plans", INVENTORY_PLANS_PATH) or {}

    def get_gm_data(self):
        return self._read_file("gm_data", GM_DATA_PATH) or []

    def get_gm_notes(self):
        return self._read_file("gm_notes", GM_NOTES_PATH) or {}

    def set_gm_notes(self, data):
        self._write_async("gm_notes", GM_NOTES_PATH, data)

    def get_emails(self):
        return self._read_file("emails", EMAILS_PATH) or []

    def set_emails(self, emails):
        new_emails = list(emails)
        lock = self._get_lock("emails")
        with lock:
            self._cache["emails"] = (new_emails, None)
        try:
            self._write_queue.put_nowait(("emails", EMAILS_PATH, new_emails))
        except queue.Full:
            log.warning("Очередь записи переполнена: emails")

    def add_email(self, entry):
        emails = self._read_file("emails", EMAILS_PATH) or []
        new_emails = list(emails)
        new_emails.append(entry)
        lock = self._get_lock("emails")
        with lock:
            self._cache["emails"] = (new_emails, None)
        try:
            self._write_queue.put_nowait(("emails", EMAILS_PATH, new_emails))
        except queue.Full:
            log.warning("Очередь записи переполнена: emails")
        return len(new_emails)

    # =========================================================
    # GUIDE.JSON (регламент инвентаризации)
    # =========================================================
    def get_guide(self):
        """Читает guide.json. Возвращает dict или None."""
        return self._read_file("guide", GUIDE_PATH)

    def set_guide(self, data):
        """Атомарно пишет guide.json (через очередь записи)."""
        self._write_async("guide", GUIDE_PATH, data)

    def reload_guide(self):
        """Сбрасывает кэш guide.json — следующий get_guide() перечитает файл.

        Полезно после ручной правки guide.json пользователем.
        """
        if "guide" in self._cache:
            self._cache["guide"] = (self._cache["guide"][0], None)
        else:
            self._cache["guide"] = (None, None)
        log.info("Кэш guide.json сброшен")

    def guide_exists(self):
        """Быстрая проверка: есть ли guide.json на диске."""
        return GUIDE_PATH.exists()

    def read_json_async(self, name, path, callback):
        def _bg_read():
            try:
                if not Path(path).exists():
                    with self._get_lock(name):
                        self._cache[name] = (None, None)
                    callback(None)
                    return
                try:
                    mtime = os.path.getmtime(str(path))
                except OSError:
                    mtime = None
                cached = self._cache.get(name)
                if cached is not None:
                    cached_data, cached_mtime = cached
                    if cached_mtime == mtime:
                        callback(cached_data)
                        return
                lock = self._get_lock(name)
                with lock:
                    cached = self._cache.get(name)
                    if cached is not None:
                        cached_data, cached_mtime = cached
                        if cached_mtime == mtime:
                            data = cached_data
                        else:
                            with open(str(path), "r", encoding="utf-8") as f:
                                data = json.load(f)
                            self._cache[name] = (data, mtime)
                    else:
                        with open(str(path), "r", encoding="utf-8") as f:
                            data = json.load(f)
                        self._cache[name] = (data, mtime)
                callback(data)
            except json.JSONDecodeError as e:
                log.error(f"JSON повреждён при async-чтении ({name}): {e}")
                try:
                    callback(None)
                except Exception:
                    log.exception(f"Ошибка callback для {name}")
            except (IOError, OSError) as e:
                log.warning(f"Ошибка async-чтения {name}: {e}")
                try:
                    callback(None)
                except Exception:
                    log.exception(f"Ошибка callback для {name}")
            except Exception:
                log.exception(f"Ошибка асинхронного чтения {name}")
                try:
                    callback(None)
                except Exception:
                    log.exception(f"Ошибка callback для {name}")
        try:
            self._read_executor.submit(_bg_read)
        except RuntimeError:
            log.warning("Read executor уже закрыт")

    def invalidate(self, name):
        if name in self._cache:
            self._cache[name] = (self._cache[name][0], None)

    def invalidate_all(self):
        for name in list(self._cache.keys()):
            self._cache[name] = (self._cache[name][0], None)

    @staticmethod
    def signature(data):
        if data is None:
            return None
        try:
            s = json.dumps(data, sort_keys=True)
            return hashlib.md5(s.encode("utf-8")).hexdigest()
        except Exception:
            return str(data)

    def shutdown(self):
        self._closing = True
        try:
            self._write_queue.put_nowait(None)
        except queue.Full:
            pass
        try:
            self._writer_thread.join(timeout=1.0)
        except Exception:
            pass
        try:
            self._read_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass


_data_manager = None
_data_manager_lock = threading.Lock()


def get_data_manager():
    global _data_manager
    if _data_manager is None:
        with _data_manager_lock:
            if _data_manager is None:
                _data_manager = DataManager()
    return _data_manager