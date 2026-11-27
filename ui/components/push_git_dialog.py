# ui/components/push_git_dialog.py
"""
Диалог «Push Git» — быстрая отправка файлов в репозиторий.

Что делает:
- показывает файлы из выбранной папки (по умолчанию — Рабочий стол\\Git)
- позволяет отметить нужные галочками
- кнопка «Отправить в Git» копирует их в локальный клон репозитория,
  делает commit и push

Репозиторий настраивается в data/git_push.json:
    {
        "repo_url": "git@github.com:Gefest100500/tmp-transfer.git",
        "clone_dir": "C:\\Core_V3_0\\tmp-transfer",
        "source_dir": "C:\\Users\\silchenko_as\\Nextcloud\\Desktop\\Git",
        "branch": "main"
    }

Если клона нет — он создаётся автоматически при первом push.
"""
import json
import os
import shutil
import subprocess
from datetime import datetime

from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QLineEdit, QTextEdit,
    QApplication,
)

from utils.file_utils import get_user_data_dir
from utils.logger import log

SETTINGS_NAME = "git_push.json"

CREATE_NO_WINDOW = 0
if hasattr(subprocess, "CREATE_NO_WINDOW"):
    CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW


# =========================================================
# НАСТРОЙКИ
# =========================================================
def settings_path() -> str:
    return os.path.join(get_user_data_dir(), SETTINGS_NAME)


def default_settings() -> dict:
    desktop = os.path.join(
        os.environ.get("USERPROFILE", os.path.expanduser("~")),
        "Nextcloud", "Desktop", "Git",
    )
    return {
        "repo_url": "git@github.com:Gefest100500/tmp-transfer.git",
        "clone_dir": os.path.join(os.path.dirname(get_user_data_dir()), "tmp-transfer"),
        "source_dir": desktop,
        "branch": "main",
    }


def load_settings() -> dict:
    path = settings_path()
    defaults = default_settings()
    if not os.path.isfile(path):
        return defaults
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError, OSError) as e:
        log.warning(f"push_git: не удалось прочитать настройки: {e}")
        return defaults
    return {**defaults, **data}


def save_settings(cfg: dict) -> bool:
    try:
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except (IOError, OSError) as e:
        log.error(f"push_git: не удалось сохранить настройки: {e}")
        return False


# =========================================================
# GIT
# =========================================================
def _run_git(args: list[str], cwd: str, timeout: int = 120):
    """Запускает git. Возвращает (код, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Таймаут выполнения git"
    except FileNotFoundError:
        return -2, "", "git не найден в PATH"
    except Exception as e:
        return -3, "", f"Ошибка запуска git: {e}"


class PushWorker(QThread):
    """Фоновая отправка: копирование, commit, push."""

    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(bool, str)

    def __init__(self, cfg: dict, files: list[str], clear_first: bool = False,
                 parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.files = files
        self.clear_first = clear_first

    def run(self):
        try:
            self._do_push()
        except Exception as e:
            log.exception("push_git: ошибка")
            self.finished_ok.emit(False, f"Ошибка: {e}")

    def _clear_repo(self, clone_dir: str) -> int:
        """Удаляет все файлы из репозитория, кроме .git.

        Возвращает число удалённых файлов.
        Удаляем через git rm, чтобы изменения попали в следующий commit.
        """
        removed = 0

        # Список файлов под контролем git
        code, out, err = _run_git(["ls-files"], clone_dir)
        if code != 0:
            return 0

        tracked = [line.strip() for line in out.splitlines() if line.strip()]
        if not tracked:
            return 0

        # git rm -r --cached . + физическое удаление
        code, out, err = _run_git(["rm", "-r", "-f", "--quiet", "."], clone_dir)
        if code != 0:
            # fallback: удалить руками
            for rel in tracked:
                full = os.path.join(clone_dir, rel)
                try:
                    if os.path.isfile(full):
                        os.remove(full)
                        removed += 1
                except OSError:
                    pass
            return removed

        removed = len(tracked)

        # Коммит очистки — чтобы история была честной
        stamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        _run_git(
            ["commit", "-m", f"Очистка репозитория перед новой выгрузкой ({stamp})"],
            clone_dir,
        )
        return removed

    def _do_push(self):
        cfg = self.cfg
        clone_dir = cfg["clone_dir"]
        branch = cfg.get("branch") or "main"
        repo_url = cfg["repo_url"]

        # --- 1. Клон ---
        if not os.path.isdir(os.path.join(clone_dir, ".git")):
            self.progress.emit(f"Клонирую репозиторий в {clone_dir}…")
            parent_dir = os.path.dirname(clone_dir)
            os.makedirs(parent_dir, exist_ok=True)
            code, out, err = _run_git(
                ["clone", repo_url, clone_dir], parent_dir, timeout=180
            )
            if code != 0:
                self.finished_ok.emit(False, f"Не удалось клонировать:\n{err or out}")
                return
            self.progress.emit("Репозиторий склонирован")
        else:
            self.progress.emit("Обновляю локальный клон…")
            _run_git(["fetch", "origin"], clone_dir)
            _run_git(["checkout", branch], clone_dir)
            _run_git(["pull", "--rebase", "origin", branch], clone_dir, timeout=180)

        # --- 1.5. Очистка репозитория (если просили) ---
        if self.clear_first:
            self.progress.emit("Очищаю репозиторий…")
            cleared = self._clear_repo(clone_dir)
            self.progress.emit(f"Удалено файлов: {cleared}")

        # --- 2. Копирование ---
        copied = []
        for src in self.files:
            name = os.path.basename(src)
            dst = os.path.join(clone_dir, name)
            try:
                shutil.copy2(src, dst)
                copied.append(name)
                self.progress.emit(f"Скопирован: {name}")
            except (IOError, OSError) as e:
                self.finished_ok.emit(False, f"Не удалось скопировать {name}:\n{e}")
                return

        if not copied:
            self.finished_ok.emit(False, "Нечего отправлять")
            return

        # --- 3. Add + commit ---
        code, out, err = _run_git(["add", "-A"], clone_dir)
        if code != 0:
            self.finished_ok.emit(False, f"git add:\n{err or out}")
            return

        # Есть ли изменения?
        code, out, err = _run_git(["status", "--porcelain"], clone_dir)
        if code == 0 and not out.strip():
            self.finished_ok.emit(True, "Файлы уже в репозитории — изменений нет")
            return

        stamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        msg = f"Добавлены файлы: {', '.join(copied)} ({stamp})"

        code, out, err = _run_git(["commit", "-m", msg], clone_dir)
        if code != 0:
            self.finished_ok.emit(False, f"git commit:\n{err or out}")
            return
        self.progress.emit("Изменения закоммичены")

        # --- 4. Push ---
        self.progress.emit("Отправляю на GitHub…")
        code, out, err = _run_git(
            ["push", "-u", "origin", branch], clone_dir, timeout=180
        )
        if code != 0:
            self.finished_ok.emit(False, f"git push:\n{err or out}")
            return

        self.progress.emit("Готово")
        self.finished_ok.emit(
            True,
            "Отправлено в репозиторий:\n" + "\n".join(f"• {n}" for n in copied),
        )


# =========================================================
# ДИАЛОГ
# =========================================================
class PushGitDialog(QDialog):
    """Меню отправки файлов в Git-репозиторий."""

    def __init__(self, parent=None, colors: dict | None = None):
        super().__init__(parent)

        c = colors or {}
        self._colors = {
            "bg": c.get("bg", "#1B1B1B"),
            "card": c.get("card", "#222222"),
            "text": c.get("text", "#E0E0E0"),
            "button": c.get("button", "#D42626"),
            "hover": c.get("hover", "#B71C1C"),
            "text_dim": c.get("text_dim", "#A0A0A0"),
            "border": c.get("border", "#333333"),
            "success": c.get("success", "#4CAF50"),
            "error": c.get("error", "#FF5252"),
        }

        self.cfg = load_settings()
        self._worker = None
        self._busy = False

        self.setWindowTitle("Push Git — Core V3.1")
        self.setModal(True)
        self.resize(880, 640)
        self.setMinimumSize(760, 520)

        self.setStyleSheet(f"""
            QDialog {{ background-color: {self._colors['bg']}; }}
            QLabel {{ color: {self._colors['text']}; }}
            QLineEdit {{
                background-color: {self._colors['bg']};
                color: {self._colors['text']};
                border: 1px solid {self._colors['border']};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {self._colors['button']}; }}
            QListWidget {{
                background-color: {self._colors['bg']};
                color: {self._colors['text']};
                border: 1px solid {self._colors['border']};
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{ padding: 7px; border-radius: 4px; }}
            QListWidget::item:hover {{ background-color: {self._colors['border']}; }}
            QTextEdit {{
                background-color: {self._colors['bg']};
                color: {self._colors['text_dim']};
                border: 1px solid {self._colors['border']};
                border-radius: 8px;
                padding: 8px;
                font-family: Consolas;
                font-size: 12px;
            }}
        """)

        self._setup_ui()
        self._reload_files()
        self._apply_dark_title_bar()

    # ---------------------------------------------------------
    def _apply_dark_title_bar(self):
        try:
            import ctypes
            hwnd = int(self.winId())
            value = ctypes.c_int(1)
            for attr in (20, 19):
                result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
                )
                if result == 0:
                    break
        except Exception:
            pass

    # ---------------------------------------------------------
    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(12)

        title = QLabel("PUSH В GIT", self)
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        # --- Репозиторий ---
        repo_card = QFrame(self)
        repo_card.setStyleSheet(f"""
            QFrame {{
                background-color: {self._colors['card']};
                border: 1px solid {self._colors['border']};
                border-radius: 10px;
            }}
        """)
        repo_layout = QVBoxLayout(repo_card)
        repo_layout.setContentsMargins(14, 12, 14, 12)
        repo_layout.setSpacing(6)

        lbl_repo = QLabel("Репозиторий:", repo_card)
        lbl_repo.setStyleSheet(f"color: {self._colors['text_dim']}; font-size: 11px;")
        repo_layout.addWidget(lbl_repo)

        self.edit_repo = QLineEdit(self.cfg["repo_url"], repo_card)
        self.edit_repo.setReadOnly(True)
        repo_layout.addWidget(self.edit_repo)

        lbl_clone = QLabel("Локальный клон:", repo_card)
        lbl_clone.setStyleSheet(f"color: {self._colors['text_dim']}; font-size: 11px;")
        repo_layout.addWidget(lbl_clone)

        self.edit_clone = QLineEdit(self.cfg["clone_dir"], repo_card)
        self.edit_clone.textChanged.connect(self._on_paths_changed)
        repo_layout.addWidget(self.edit_clone)

        outer.addWidget(repo_card)

        # --- Папка-источник ---
        source_row = QHBoxLayout()
        source_row.setSpacing(8)

        lbl_src = QLabel("Папка с файлами:", self)
        lbl_src.setStyleSheet(f"color: {self._colors['text_dim']}; font-size: 12px;")
        source_row.addWidget(lbl_src)

        self.edit_source = QLineEdit(self.cfg["source_dir"], self)
        self.edit_source.textChanged.connect(self._on_paths_changed)
        source_row.addWidget(self.edit_source, 1)

        btn_browse = QPushButton("Обзор…", self)
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.setMinimumHeight(32)
        btn_browse.setStyleSheet(self._btn_style())
        btn_browse.clicked.connect(self._browse_source)
        source_row.addWidget(btn_browse)

        btn_reload = QPushButton("Обновить", self)
        btn_reload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reload.setMinimumHeight(32)
        btn_reload.setStyleSheet(self._btn_style())
        btn_reload.clicked.connect(self._reload_files)
        source_row.addWidget(btn_reload)

        outer.addLayout(source_row)

        # --- Список файлов ---
        self.list_files = QListWidget(self)
        self.list_files.setSelectionMode(
            QListWidget.SelectionMode.NoSelection
        )
        outer.addWidget(self.list_files, 1)

        # --- Кнопки «все/ничего» ---
        sel_row = QHBoxLayout()
        sel_row.setSpacing(8)

        btn_all = QPushButton("Выбрать все", self)
        btn_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_all.setMinimumHeight(28)
        btn_all.setStyleSheet(self._btn_style())
        btn_all.clicked.connect(lambda: self._set_all(True))
        sel_row.addWidget(btn_all)

        btn_none = QPushButton("Снять все", self)
        btn_none.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_none.setMinimumHeight(28)
        btn_none.setStyleSheet(self._btn_style())
        btn_none.clicked.connect(lambda: self._set_all(False))
        sel_row.addWidget(btn_none)

        sel_row.addStretch()

        self.lbl_count = QLabel("Файлов выбрано: 0", self)
        self.lbl_count.setStyleSheet(
            f"color: {self._colors['text_dim']}; font-size: 12px;"
        )
        sel_row.addWidget(self.lbl_count)

        outer.addLayout(sel_row)

        # --- Лог ---
        self.log_view = QTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(110)
        outer.addWidget(self.log_view)

        # --- Кнопки действий ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self.btn_push = QPushButton("Отправить в Git", self)
        self.btn_push.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_push.setMinimumHeight(40)
        self.btn_push.setMinimumWidth(200)
        self.btn_push.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._colors['button']};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {self._colors['hover']}; }}
            QPushButton:disabled {{
                background-color: {self._colors['border']};
                color: {self._colors['text_dim']};
            }}
        """)
        self.btn_push.clicked.connect(self._start_push)
        btn_row.addWidget(self.btn_push)

        btn_close = QPushButton("Закрыть", self)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setMinimumHeight(40)
        btn_close.setMinimumWidth(120)
        btn_close.setStyleSheet(self._btn_style())
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)

        outer.addLayout(btn_row)

    def _btn_style(self):
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {self._colors['text_dim']};
                border: 1px solid {self._colors['border']};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {self._colors['card']};
                color: {self._colors['text']};
            }}
        """

    # ---------------------------------------------------------
    # ФАЙЛЫ
    # ---------------------------------------------------------
    def _on_paths_changed(self):
        self.cfg["clone_dir"] = self.edit_clone.text().strip()
        self.cfg["source_dir"] = self.edit_source.text().strip()

    def _browse_source(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Выберите папку с файлами", self.edit_source.text()
        )
        if folder:
            self.edit_source.setText(folder)
            self._reload_files()

    def _reload_files(self):
        folder = self.edit_source.text().strip()
        self.list_files.clear()

        if not os.path.isdir(folder):
            item = QListWidgetItem(f"Папка не найдена: {folder}")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_files.addItem(item)
            self._update_count()
            return

        try:
            names = sorted(
                f for f in os.listdir(folder)
                if os.path.isfile(os.path.join(folder, f))
            )
        except (OSError, PermissionError) as e:
            item = QListWidgetItem(f"Нет доступа: {e}")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_files.addItem(item)
            self._update_count()
            return

        if not names:
            item = QListWidgetItem("В папке нет файлов")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_files.addItem(item)
            self._update_count()
            return

        for name in names:
            full = os.path.join(folder, name)
            try:
                size = os.path.getsize(full)
                size_text = (
                    f"{size / 1024 / 1024:.1f} МБ" if size > 1024 * 1024
                    else f"{size / 1024:.0f} КБ"
                )
            except OSError:
                size_text = "—"

            item = QListWidgetItem(f"  {name}    ({size_text})")
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, full)
            self.list_files.addItem(item)

        self.list_files.itemChanged.connect(self._update_count)
        self._update_count()

    def _set_all(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.list_files.count()):
            item = self.list_files.item(i)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(state)
        self._update_count()

    def _selected_files(self) -> list[str]:
        result = []
        for i in range(self.list_files.count()):
            item = self.list_files.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                path = item.data(Qt.ItemDataRole.UserRole)
                if path:
                    result.append(path)
        return result

    def _update_count(self):
        n = len(self._selected_files())
        self.lbl_count.setText(f"Файлов выбрано: {n}")
        self.btn_push.setEnabled(n > 0 and not self._busy)

    # ---------------------------------------------------------
    # PUSH
    # ---------------------------------------------------------
    def _start_push(self):
        files = self._selected_files()
        if not files:
            return

        # Спрашиваем про очистку репозитория
        from ui.components.dialogs import CustomMessageBox
        c = self._colors
        answer = CustomMessageBox(
            self,
            "Очистить репозиторий?",
            "Будет отправлено файлов: " + str(len(files)) + chr(10) + chr(10) +
            "• «Очистить и залить» — старые файлы удаляются," + chr(10) +
            "   заливаются только выбранные." + chr(10) + chr(10) +
            "• «Добавить» — старые файлы остаются," + chr(10) +
            "   новые добавляются рядом.",
            "question",
            buttons=[
                ("Очистить и залить", "primary"),
                ("Добавить", "secondary"),
                ("Отмена", "ghost"),
            ],
            bg=c["bg"], card=c["card"], text=c["text"],
            button=c["button"], hover=c["hover"],
            text_dim=c["text_dim"], border=c["border"],
        ).exec()


        clear_first = False
        if answer == 0:
            clear_first = True
        elif answer == 1:
            clear_first = False
        else:
            return

        self._busy = True
        self.btn_push.setEnabled(False)
        self.btn_push.setText("Отправляю…")
        self.log_view.clear()
        self._log("Начало отправки")

        self.cfg["clone_dir"] = self.edit_clone.text().strip()
        self.cfg["source_dir"] = self.edit_source.text().strip()
        save_settings(self.cfg)

        self._worker = PushWorker(self.cfg, files, clear_first, self)
        self._worker.progress.connect(self._log)
        self._worker.finished_ok.connect(self._on_push_done)
        self._worker.start()

    def _log(self, text: str):
        self.log_view.append(text)
        QApplication.processEvents()

    def _on_push_done(self, ok: bool, message: str):
        self._busy = False
        self.btn_push.setText("Отправить в Git")
        self._update_count()

        color = self._colors["success"] if ok else self._colors["error"]
        self.log_view.append("")
        self.log_view.append(f"=== {'ГОТОВО' if ok else 'ОШИБКА'} ===")
        self.log_view.append(message)
        self.log_view.setStyleSheet(
            self.log_view.styleSheet() + f"QTextEdit {{ color: {color}; }}"
        )

        self._worker = None
