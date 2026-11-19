# core/guide_manager.py
"""
Менеджер вкладки «Регламент» (GuideTab).

Загружает data/guide.json, валидирует структуру, кэширует HTML
по id секции, рендерит блоки (text, warning, steps, image, action),
ищет по разделам.

Не зависит от PyQt6 — можно тестировать без QApplication.

ИЗМЕНЕНИЯ:
- Первая версия.
"""
import json
import os
import re
from pathlib import Path
from typing import Optional

from utils.file_utils import get_user_data_dir
from utils.logger import log


# =========================================================
# ПУТИ
# =========================================================
DATA_DIR = Path(get_user_data_dir())
GUIDE_PATH = DATA_DIR / "guide.json"
IMAGES_DIR = DATA_DIR / "images"


# =========================================================
# ПУСТАЯ СТРУКТУРА (fallback)
# =========================================================
_EMPTY_GUIDE = {
    "guide": {
        "title": "Регламент инвентаризации ГМ",
        "version": "3.0",
        "sections": [],
    }
}


# =========================================================
# МЕНЕДЖЕР
# =========================================================
class GuideManager:
    """Загрузка, валидация, кэш и рендер guide.json."""

    def __init__(self, guide_path: Optional[str] = None):
        self._guide_path = Path(guide_path) if guide_path else GUIDE_PATH
        self._guide: dict = _EMPTY_GUIDE
        self._html_cache: dict[str, str] = {}
        self._loaded = False
        self._load()

    # =========================================================
    # ЗАГРУЗКА И ВАЛИДАЦИЯ
    # =========================================================
    def _load(self):
        """Читает guide.json. При ошибке — пустая структура."""
        self._html_cache.clear()
        self._loaded = False

        if not self._guide_path.exists():
            log.warning(f"guide.json не найден: {self._guide_path}")
            self._guide = _EMPTY_GUIDE
            return

        try:
            with open(self._guide_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            log.error(f"guide.json повреждён: {e}")
            self._guide = _EMPTY_GUIDE
            return
        except (IOError, OSError) as e:
            log.warning(f"Ошибка чтения guide.json: {e}")
            self._guide = _EMPTY_GUIDE
            return

        if not self._validate(data):
            log.error("guide.json не прошёл валидацию — используется пустая структура")
            self._guide = _EMPTY_GUIDE
            return

        self._guide = data
        self._loaded = True
        log.info(
            f"guide.json загружен: {len(self.sections())} разделов, "
            f"версия {self.version()}"
        )

    def _validate(self, data) -> bool:
        """Проверяет структуру: guide → sections → blocks, уникальные id."""
        if not isinstance(data, dict):
            return False
        guide = data.get("guide")
        if not isinstance(guide, dict):
            return False
        sections = guide.get("sections")
        if not isinstance(sections, list):
            return False

        seen_ids = set()
        for sec in sections:
            if not isinstance(sec, dict):
                return False
            sid = sec.get("id")
            if not isinstance(sid, str) or not sid:
                return False
            if sid in seen_ids:
                log.error(f"guide.json: дубликат id секции '{sid}'")
                return False
            seen_ids.add(sid)

            if not isinstance(sec.get("title"), str):
                return False
            if not isinstance(sec.get("blocks"), list):
                return False

            for block in sec["blocks"]:
                if not isinstance(block, dict):
                    return False
                btype = block.get("type")
                if btype not in ("text", "warning", "steps", "image", "action"):
                    log.warning(f"guide.json: неизвестный тип блока '{btype}' в '{sid}'")
                    return False
                if btype in ("text", "warning"):
                    if not isinstance(block.get("content"), str):
                        return False
                elif btype == "steps":
                    if not isinstance(block.get("content"), list):
                        return False
                elif btype == "image":
                    if not isinstance(block.get("path"), str):
                        return False
                elif btype == "action":
                    if not isinstance(block.get("action"), str):
                        return False
                    if not isinstance(block.get("label"), str):
                        return False
        return True

    # =========================================================
    # ПУБЛИЧНЫЕ СВОЙСТВА
    # =========================================================
    def is_loaded(self) -> bool:
        return self._loaded

    def title(self) -> str:
        return self._guide["guide"].get("title", "Регламент")

    def version(self) -> str:
        return self._guide["guide"].get("version", "")

    def sections(self) -> list[dict]:
        return self._guide["guide"].get("sections", [])

    def get_section(self, section_id: str) -> Optional[dict]:
        for sec in self.sections():
            if sec["id"] == section_id:
                return sec
        return None

    def section_title(self, section_id: str) -> str:
        sec = self.get_section(section_id)
        return sec["title"] if sec else ""

    # =========================================================
    # РЕНДЕР
    # =========================================================
    def render_section(self, section_id: str) -> str:
        """Возвращает HTML для секции. Кэширует по id."""
        if section_id in self._html_cache:
            return self._html_cache[section_id]

        sec = self.get_section(section_id)
        if sec is None:
            return "<body><p>Раздел не найден</p></body>"

        html = self._render(sec)
        self._html_cache[section_id] = html
        return html

    def _render(self, section: dict) -> str:
        parts = ["<body>"]
        parts.append(f"<h1>{self._escape(section.get('title', ''))}</h1>")

        for block in section.get("blocks", []):
            btype = block.get("type")
            try:
                if btype == "text":
                    parts.append(self._render_text(block['content']))
                elif btype == "warning":
                    parts.append(
                        f"<div class='warning'>{self._render_warning(block['content'])}</div>"
                    )
                elif btype == "steps":
                    items = "".join(
                        f"<li>{self._escape(str(s))}</li>"
                        for s in block.get("content", [])
                    )
                    parts.append(f"<ol>{items}</ol>")
                elif btype == "image":
                    parts.append(self._render_image(block))
                elif btype == "action":
                    action = block.get("action", "")
                    label = self._escape(block.get("label", ""))
                    parts.append(
                        f"<p><a href='action://{self._escape(action)}'>{label}</a></p>"
                    )
            except Exception as e:
                log.warning(
                    f"guide_manager: ошибка рендера блока {btype} "
                    f"в '{section.get('id')}': {e}"
                )

        parts.append("</body>")
        return "".join(parts)

    def _render_image(self, block: dict) -> str:
        """Картинка: относительный путь в JSON → абсолютный для QTextBrowser."""
        rel_path = block.get("path", "")
        abs_path = os.path.abspath(os.path.join(str(DATA_DIR), rel_path))
        abs_path_url = Path(abs_path).as_uri()  # file:///...
        width = block.get("width", 600)
        html = f"<img src='{abs_path_url}' width='{width}'>"
        caption = block.get("caption")
        if caption:
            html += f"<p class='caption'>{self._escape(caption)}</p>"
        return html

    # ---------------------------------------------------------
    # ТЕЗИСНОЕ ДЕЛЕНИЕ ТЕКСТА
    # ---------------------------------------------------------
    #: Разделитель для списка действий «A → B → C».
    ARROW = "→"

    def _render_text(self, content: str) -> str:
        """Разбивает сплошной текст на тезисы.

        Правила:
        - предложения делятся по «. » и выводятся отдельными пунктами;
        - если предложение содержит цепочку «A → B → C», она выводится
          отдельным списком шагов;
        - одиночное короткое предложение остаётся абзацем.
        """
        text = (content or "").strip()
        if not text:
            return ""

        sentences = self._split_sentences(text)

        if len(sentences) == 1:
            only = sentences[0]
            if self.ARROW in only:
                return f"<p>{self._render_chain(only)}</p>"
            return f"<p>{self._escape(only)}</p>"

        parts = ["<ul>"]
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if self.ARROW in sentence:
                parts.append(f"<li>{self._render_chain(sentence)}</li>")
            else:
                parts.append(f"<li>{self._escape(sentence)}</li>")
        parts.append("</ul>")
        return "".join(parts)

    def _render_warning(self, content: str) -> str:
        """Предупреждение: заголовок без эмодзи + тезисы."""
        text = (content or "").strip()
        if not text:
            return ""

        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return f"<p>{self._escape(text)}</p>"

        items = "".join(
            f"<li>{self._escape(s)}</li>" for s in sentences if s.strip()
        )
        return f"<p><b>Проверить</b></p><ul>{items}</ul>"

    def _render_chain(self, sentence: str) -> str:
        """«A → B → C» превращает в нумерованные шаги внутри пункта."""
        steps = [s.strip() for s in sentence.split(self.ARROW) if s.strip()]
        if len(steps) < 2:
            return self._escape(sentence)

        joined = " &rarr; ".join(self._escape(s) for s in steps)
        return joined

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Делит текст на предложения, не ломая аббревиатуры и числа."""
        if not text:
            return []

        # Точка, вопросительный или восклицательный знак + пробел + заглавная.
        chunks = re.split(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z«(])", text)
        return [c.strip() for c in chunks if c.strip()]

    @staticmethod
    def _escape(text: str) -> str:
        """Минимальное экранирование HTML (без изменения кавычек в href)."""
        if not isinstance(text, str):
            text = str(text)
        return (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )

    # =========================================================
    # ПОИСК
    # =========================================================
    def search(self, query: str) -> list[dict]:
        """Ищет query по title и содержимому блоков.

        Возвращает список:
        [
            {"id": ..., "title": ..., "snippet": ...},
            ...
        ]
        Сниппет — фрагмент текста вокруг первого совпадения.
        """
        if not query:
            return []
        q = query.lower().strip()
        if not q:
            return []

        results = []
        for sec in self.sections():
            sid = sec["id"]
            title = sec.get("title", "")
            title_match = q in title.lower()

            snippet = ""
            content_match = False
            for block in sec.get("blocks", []):
                text = self._block_to_text(block)
                if not text:
                    continue
                idx = text.lower().find(q)
                if idx >= 0:
                    content_match = True
                    snippet = self._make_snippet(text, idx, len(q))
                    break

            if title_match or content_match:
                if not snippet:
                    snippet = self._make_snippet(title, 0, 0)
                results.append({
                    "id": sid,
                    "title": title,
                    "snippet": snippet,
                })
        return results

    @staticmethod
    def _block_to_text(block: dict) -> str:
        """Извлекает текст из блока для поиска."""
        btype = block.get("type")
        if btype in ("text", "warning"):
            return block.get("content", "")
        if btype == "steps":
            return " ".join(str(s) for s in block.get("content", []))
        if btype == "action":
            return block.get("label", "")
        if btype == "image":
            return block.get("caption", "")
        return ""

    @staticmethod
    def _make_snippet(text: str, idx: int, qlen: int, radius: int = 40) -> str:
        """Фрагмент вокруг совпадения с многоточиями."""
        start = max(0, idx - radius)
        end = min(len(text), idx + qlen + radius)
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(text) else ""
        return f"{prefix}{text[start:end]}{suffix}"

    # =========================================================
    # ПЕРЕЗАГРУЗКА
    # =========================================================
    def reload(self):
        """Перечитывает guide.json (например, после правки файла)."""
        self._load()


# =========================================================
# SINGLETON
# =========================================================
_guide_manager: Optional[GuideManager] = None


def get_guide_manager() -> GuideManager:
    """Возвращает единственный экземпляр GuideManager."""
    global _guide_manager
    if _guide_manager is None:
        _guide_manager = GuideManager()
    return _guide_manager


def reset_guide_manager():
    """Сбрасывает singleton. Для тестов."""
    global _guide_manager
    _guide_manager = None