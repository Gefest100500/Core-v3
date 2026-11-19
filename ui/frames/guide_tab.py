# ui/frames/guide_tab.py
"""
Вкладка «Регламент» (GuideTab).

Устройство:
- слева QListWidget (оглавление) + поиск;
- справа QTextBrowser с HTML-разделом;
- данные: data/guide.json, логика: core/guide_manager.py.

Стиль приведён к общему языку Core:
- шрифт Segoe UI из self.FONTS, а не хардкод;
- цвета только из self.COLORS;
- одинаковые отступы, радиусы и размеры;
- подсветка поиска — жёлтым фоном поверх текста (а не только курсором);
- встроенный CSS документа собирается из палитры Core.
"""
from collections import OrderedDict

from PyQt6.QtCore import Qt, QUrl, QSettings
from PyQt6.QtGui import (
    QTextDocument, QTextCharFormat, QColor, QTextCursor, QBrush, QPainter, QPen,
)
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QSplitter, QListWidget, QListWidgetItem,
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import SecondaryButton, StyledEntry
from core.guide_manager import get_guide_manager
from utils.logger import log

SETTINGS_ORG = "SilchenkoAleksey"
SETTINGS_APP = "CoreV3"
LAST_SECTION_KEY = "guide_last_section"

ROOT_MARGIN = 16
PANEL_MARGIN = 0
SPLITTER_WIDTH = 2
TREE_PADDING = 8
ITEM_PADDING = 8
BORDER_RADIUS = 8

def build_document_css(colors: dict, fonts: dict) -> str:
    """CSS для QTextBrowser, собранный из палитры и шрифтов Core.

    QTextDocument не умеет web-safe CSS целиком: поддерживаются базовые
    свойства (размеры, цвета, отступы, границы). Поэтому здесь только то,
    что QTextDocument реально применяет.
    """
    text = colors.get("text", "#E0E0E0")
    text_dim = colors.get("text_dim", "#A0A0A0")
    border = colors.get("border", "#333333")
    error = colors.get("error", "#FF5252")
    button = colors.get("button", "#D42626")

    family = fonts.get("label").family() if fonts.get("label") else "Segoe UI"
    base_size = fonts.get("label").pointSize() if fonts.get("label") else 10
    h1_size = fonts.get("title").pointSize() if fonts.get("title") else 16
    h2_size = fonts.get("subtitle").pointSize() if fonts.get("subtitle") else 12

    return f"""
    body {{ margin: 0; padding: 0; color: {text}; }}
    h1 {{ margin: 0 0 14px 0; font-size: {h1_size}pt; color: {text}; }}
    h2 {{ margin: 18px 0 8px 0; font-size: {h2_size}pt; color: {text}; }}
    p  {{ margin: 8px 0; line-height: 160%; font-size: {base_size}pt; }}
    ul, ol {{ margin: 8px 0 12px 0; }}
    li {{ margin-bottom: 6px; line-height: 160%; font-size: {base_size}pt; }}
    a {{ color: {button}; text-decoration: none; }}
    table {{ border-collapse: collapse; margin: 10px 0; }}
    th, td {{ border: 1px solid {border}; padding: 6px 10px; font-size: {base_size}pt; }}
    th {{ color: {text}; }}
    .warning {{
        color: {error};
        background-color: #2A2020;
        border: 1px solid {error};
        padding: 10px 12px;
        margin: 12px 0;
    }}
    .caption {{ color: {text_dim}; font-size: 9pt; margin: 4px 0 12px 0; }}
    """

class GuideTextBrowser(QTextBrowser):
    """QTextBrowser без рамки: рамку и фон задаёт вкладка."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.viewport().setAutoFillBackground(False)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)

class GuideTab(BaseFrame):
    TITLE = "Регламент"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._guide = get_guide_manager()
        self._current_section_id = None
        self._current_query = ""

        self._setup_ui()
        self._build_tree()
        self._restore_last_section()

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(ROOT_MARGIN, ROOT_MARGIN, ROOT_MARGIN, ROOT_MARGIN)
        root.setSpacing(10)

        header = QLabel("Регламент инвентаризации", self)
        header.setFont(self.FONTS["title"])
        header.setStyleSheet(f"color: {self.COLORS.get('text', '#E0E0E0')};")
        root.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(SPLITTER_WIDTH)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background-color: {self.COLORS.get('border', '#333333')}; }}"
        )

        # ---------------- ЛЕВАЯ ПАНЕЛЬ ----------------
        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(PANEL_MARGIN, PANEL_MARGIN, PANEL_MARGIN, PANEL_MARGIN)
        left_layout.setSpacing(8)

        self.search_entry = StyledEntry("Поиск по регламенту...")
        self.search_entry.textChanged.connect(self._on_search_changed)
        left_layout.addWidget(self.search_entry)

        card = self.COLORS.get("card", "#222222")
        text = self.COLORS.get("text", "#E0E0E0")
        text_dim = self.COLORS.get("text_dim", "#A0A0A0")
        border = self.COLORS.get("border", "#333333")
        sidebar = self.COLORS.get("sidebar", "#2A2A2A")
        button = self.COLORS.get("button", "#D42626")

        # QListWidget, а не QTreeWidget: у дерева Qt заливает цветом
        # выделения область слева от текста (ветку), и убрать это через
        # QSS не получается. Плоский список групп и разделов решает
        # проблему целиком.
        self.list = QListWidget(left)
        self.list.setFrameShape(QListWidget.Shape.NoFrame)
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.setVerticalScrollMode(
            QListWidget.ScrollMode.ScrollPerPixel
        )
        self.list.setSpacing(0)

        self.list.setStyleSheet(f"""
            QListWidget {{
                background-color: {card};
                color: {text};
                border: 1px solid {border};
                border-radius: {BORDER_RADIUS}px;
                outline: 0;
                padding: 6px;
            }}
            QListWidget::item {{
                padding: 6px 10px;
                border: 0;
                border-radius: 6px;
                margin: 1px 0;
            }}
            QListWidget::item:selected {{
                background-color: {button};
                color: #FFFFFF;
            }}
            QListWidget::item:hover:!selected {{
                background-color: {sidebar};
            }}
            QListWidget QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 4px 2px 4px 0;
            }}
            QListWidget QScrollBar::handle:vertical {{
                background: {border};
                border-radius: 4px;
                min-height: 28px;
            }}
            QListWidget QScrollBar::handle:vertical:hover {{
                background: {text_dim};
            }}
            QListWidget QScrollBar::add-line:vertical,
            QListWidget QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QListWidget QScrollBar::add-page:vertical,
            QListWidget QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)
        self.list.itemClicked.connect(self._on_item_clicked)
        left_layout.addWidget(self.list, 1)

        splitter.addWidget(left)

        # ---------------- ПРАВАЯ ПАНЕЛЬ ----------------
        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(PANEL_MARGIN, PANEL_MARGIN, PANEL_MARGIN, PANEL_MARGIN)
        right_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.section_title = QLabel("", right)
        self.section_title.setFont(self.FONTS["subtitle"])
        self.section_title.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )
        top_row.addWidget(self.section_title)
        top_row.addStretch()

        self.btn_reload = SecondaryButton(
            "Обновить", on_click=self._on_reload_clicked, icon_name="refresh"
        )
        self.btn_reload.setMinimumHeight(32)
        self.btn_reload.setMinimumWidth(140)
        top_row.addWidget(self.btn_reload)

        right_layout.addLayout(top_row)

        self.browser = GuideTextBrowser(right)
        self.browser.anchorClicked.connect(self._on_anchor_clicked)
        self.browser.document().setDefaultStyleSheet(
            build_document_css(self.COLORS, self.FONTS)
        )
        self._apply_browser_theme()
        right_layout.addWidget(self.browser, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([280, 720])

        root.addWidget(splitter, 1)

    def _apply_browser_theme(self):
        """Фон, рамка и полоса прокрутки браузера — в палитре Core."""
        card = self.COLORS.get("card", "#222222")
        border = self.COLORS.get("border", "#333333")
        button = self.COLORS.get("button", "#D42626")
        text_dim = self.COLORS.get("text_dim", "#A0A0A0")

        self.browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {card};
                border: 1px solid {border};
                border-radius: {BORDER_RADIUS}px;
                padding: 20px;
                selection-background-color: {button};
                selection-color: #FFFFFF;
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {border};
                min-height: 24px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {text_dim};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

    # =========================================================
    # ДЕРЕВО
    # =========================================================
    def _build_tree(self):
        """Строит список: жирные заголовки групп + пункты разделов."""
        self.list.clear()

        if not self._guide.is_loaded():
            self._add_placeholder("guide.json не найден")
            return

        sections = self._guide.sections()
        if not sections:
            self._add_placeholder("Разделы отсутствуют")
            return

        groups: "OrderedDict[str, list[dict]]" = OrderedDict()
        for sec in sections:
            title = sec.get("title", "")
            prefix = title.split(":", 1)[0].strip() if ":" in title else ""
            groups.setdefault(prefix, []).append(sec)

        for prefix, secs in groups.items():
            if prefix:
                header = QListWidgetItem(prefix)
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                font = header.font()
                font.setBold(True)
                font.setPointSizeF(font.pointSizeF() + 0.5)
                header.setFont(font)
                header.setForeground(
                    QBrush(QColor(self.COLORS.get("text", "#E0E0E0")))
                )
                header.setSizeHint(QSize(0, 34))
                self.list.addItem(header)

            for sec in secs:
                title = self._short_title(sec) if prefix else sec.get("title", "")
                item = QListWidgetItem(("    " + title) if prefix else title)
                item.setData(Qt.ItemDataRole.UserRole, sec["id"])
                item.setToolTip(sec.get("title", ""))
                item.setSizeHint(QSize(0, 30))
                self.list.addItem(item)

    def _add_placeholder(self, text: str):
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.list.addItem(item)

    @staticmethod
    def _short_title(sec: dict) -> str:
        title = sec.get("title", "")
        return title.split(":", 1)[1].strip() if ":" in title else title

    def _restore_last_section(self):
        last_id = self._settings.value(LAST_SECTION_KEY, "")
        item = self._find_item_by_id(str(last_id)) if last_id else None
        if item is None:
            item = self._first_selectable_item()
        if item is not None:
            self.list.setCurrentItem(item)
            self._select_section(item.data(Qt.ItemDataRole.UserRole))

    def _first_selectable_item(self):
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(Qt.ItemDataRole.UserRole):
                return item
        return None

    def _find_item_by_id(self, section_id: str):
        if not section_id:
            return None
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == section_id:
                return item
        return None

    # =========================================================
    # ВЫБОР РАЗДЕЛА
    # =========================================================
    def _on_item_clicked(self, item):
        if item is None:
            return
        self._select_section(item.data(Qt.ItemDataRole.UserRole))

    def _select_section(self, section_id):
        if not section_id:
            return

        self._current_section_id = section_id
        self.browser.setHtml(self._guide.render_section(section_id))
        self.section_title.setText(self._guide.section_title(section_id))

        if self._current_query:
            self._highlight_all(self._current_query)
        else:
            self.browser.moveCursor(QTextCursor.MoveOperation.Start)

    # =========================================================
    # ССЫЛКИ
    # =========================================================
    def _on_anchor_clicked(self, url: QUrl):
        scheme = url.scheme()

        if scheme == "action":
            self._handle_action(url.toString())
            return

        if url.hasFragment() and scheme in ("", "http", "https"):
            self.browser.scrollToAnchor(url.fragment())
            return

        if scheme in ("http", "https"):
            try:
                import webbrowser
                webbrowser.open(url.toString())
            except Exception as e:
                log.warning(f"guide_tab: не удалось открыть ссылку: {e}")

    def _handle_action(self, url: str):
        try:
            tab_name = url.replace("action://", "", 1)
            if not tab_name:
                return
            if hasattr(self.app, "show_tab"):
                self.app.show_tab(tab_name)
            else:
                log.warning(f"guide_tab: action '{tab_name}' — нет app.show_tab")
        except Exception as e:
            log.exception(f"guide_tab: ошибка обработки action: {e}")

    # =========================================================
    # ПОИСК
    # =========================================================
    def _on_search_changed(self, text: str):
        self._current_query = text.strip()
        self._filter_tree(self._current_query)

        if self._current_query:
            self._highlight_all(self._current_query)

    def _filter_tree(self, query: str):
        """Скрывает пункты, не подходящие под запрос; группы — по остатку."""
        q = query.lower()
        group_has_match = True  # до первой группы

        for i in range(self.list.count()):
            item = self.list.item(i)
            sid = item.data(Qt.ItemDataRole.UserRole)

            if not sid:
                # заголовок группы: решаем по накопленному флагу предыдущей
                if not q:
                    item.setHidden(False)
                item.setHidden(False if not q else not group_has_match)
                group_has_match = False
                continue

            match = self._section_matches(sid, q) if q else True
            item.setHidden(bool(q) and not match)
            if match:
                group_has_match = True

    def _section_matches(self, section_id: str, q: str) -> bool:
        if not q:
            return True
        sec = self._guide.get_section(section_id)
        if sec is None:
            return False
        if q in sec.get("title", "").lower():
            return True
        for block in sec.get("blocks", []):
            if q in self._guide._block_to_text(block).lower():
                return True
        return False

    def _highlight_all(self, query: str):
        """Подсвечивает ВСЕ вхождения подсветкой фона, а не только первое."""
        if not query:
            return

        doc: QTextDocument = self.browser.document()

        # Снимаем прошлые подсветки
        clear_cursor = QTextCursor(doc)
        clear_cursor.select(QTextCursor.SelectionType.Document)
        clear_format = QTextCharFormat()
        clear_format.setBackground(QColor(Qt.GlobalColor.transparent))
        clear_cursor.mergeCharFormat(clear_format)

        highlight = QTextCharFormat()
        highlight.setBackground(QColor("#5A4A1A"))
        highlight.setForeground(QColor("#FFFFFF"))

        cursor = QTextCursor(doc)
        first = None
        while True:
            cursor = doc.find(query, cursor)
            if cursor.isNull():
                break
            if first is None:
                first = QTextCursor(cursor)
            cursor.mergeCharFormat(highlight)

        if first is not None:
            self.browser.setTextCursor(first)
            self.browser.ensureCursorVisible()

    # =========================================================
    # ОБНОВЛЕНИЕ
    # =========================================================
    def _on_reload_clicked(self):
        try:
            self.app.data_manager.reload_guide()
            self._guide.reload()
            self._build_tree()
            self._restore_last_section()
            self.set_status("Регламент обновлён", self.COLORS.get("success", "#4CAF50"))
        except Exception as e:
            log.exception("guide_tab: ошибка обновления")
            self.show_error("Ошибка", f"Не удалось обновить регламент:\n{e}")

    # =========================================================
    # ХУКИ ЖИЗНЕННОГО ЦИКЛА
    # =========================================================
    def refresh(self):
        """Вызывается AuditApp при КАЖДОМ входе на вкладку.

        Возвращает вкладку в исходное состояние: очищает поиск,
        снимает фильтр, прокручивает список и текст в начало.
        """
        self._reset_view_state()

        if self._guide.is_loaded():
            return

        self._guide.reload()
        self._build_tree()
        self._restore_last_section()

    def _reset_view_state(self):
        """Сброс поиска, прокрутки и подсветки к умолчанию."""
        # 1. Очистить поле поиска (сбрасывается и фильтр списка)
        if self.search_entry.text():
            self.search_entry.blockSignals(True)
            self.search_entry.clear()
            self.search_entry.blockSignals(False)

        self._current_query = ""
        self._filter_tree("")

        # 2. Прокрутить список разделов в начало
        try:
            self.list.scrollToTop()
        except Exception:
            pass

        # 3. Прокрутить текст раздела в начало и снять подсветку
        try:
            self.browser.moveCursor(QTextCursor.MoveOperation.Start)
            self.browser.verticalScrollBar().setValue(0)
        except Exception:
            pass

    def on_hide(self):
        self._save_last_section()

    def on_close(self):
        self._save_last_section()

    def _save_last_section(self):
        try:
            if self._current_section_id:
                self._settings.setValue(LAST_SECTION_KEY, self._current_section_id)
        except Exception as e:
            log.debug(f"guide_tab: не удалось сохранить раздел: {e}")
