# ui/styles.py
"""
QSS-стили для Core V3.1.

ИЗМЕНЕНИЯ:
- Добавлены глобальные правила для QProgressBar (серый).
- Убраны жёсткие padding у QLabel (чтобы не влиять на статусы).
- Для QLabel#StatusNeutral (серый текст) добавлено отдельное правило.
- Добавлены глобальные правила для QTreeWidget (оглавление GuideTab)
  и QTextBrowser (фолбэк, если локальный стиль не применился).
"""


# =========================================================
# ШАБЛОН QSS
# =========================================================
QSS_TEMPLATE = """
QMainWindow, QWidget {
    background-color: %bg%;
    color: %text%;
}

QLabel {
    background-color: transparent;
}

QStackedWidget {
    background-color: %bg%;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QScrollBar:vertical {
    background: %sidebar%;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: %border%;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: %text_dim%;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QFrame#Sidebar {
    background-color: %sidebar%;
    border: none;
}

QLabel#Logo {
    color: %text%;
    padding: 20px 0 24px 0;
    background-color: transparent;
}

/* =========================================================
   Кнопки сайдбара
   ========================================================= */
QPushButton#SidebarBtn {
    background-color: transparent;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 8px;
    padding: 10px 14px;
    padding-left: 50px;
    text-align: left;
    font-size: 13px;
}

QPushButton#SidebarBtn:hover {
    background-color: %hover%;
    border-color: %hover%;
    color: white;
}

QPushButton#SidebarBtn[active="true"] {
    background-color: %button%;
    border-color: %button%;
    color: white;
}

QPushButton#SidebarBtn[collapsed="true"] {
    text-align: center;
    padding: 0px;
    border: none;
}

QFrame#StatusBar {
    background-color: %sidebar%;
    border-top: 1px solid %border%;
}

QLabel#StatusText {
    color: %text_dim%;
    padding: 6px 16px;
    background-color: transparent;
}

QLabel#Credit {
    color: #555555;
    padding: 20px 0;
    background-color: transparent;
}

QFrame#Card {
    background-color: %card%;
    border: 1px solid %border%;
    border-radius: 10px;
}

QLabel#Title {
    color: %text%;
    padding: 8px 0 16px 0;
    background-color: transparent;
}

QLabel#Subtitle {
    color: %text%;
    background-color: transparent;
}

QPushButton {
    background-color: %button%;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
}

QPushButton:hover {
    background-color: %hover%;
}

QPushButton:disabled {
    background-color: #555555;
    color: #999999;
}

/* =========================================================
   Глобальный QProgressBar — серый, единый стиль
   ========================================================= */
QProgressBar {
    background-color: %sidebar%;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: %text%;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: %text_dim%;
    border-radius: 4px;
}

/* =========================================================
   Статусные метки (если используются)
   ========================================================= */
QLabel#StatusNeutral {
    color: %text_dim%;
    background: transparent;
}

QLabel#StatusSuccess {
    color: %text_dim%; /* серый, а не зелёный */
    background: transparent;
}

QLabel#StatusError {
    color: %error%;
    background: transparent;
}

/* =========================================================
   QComboBox
   ========================================================= */
QComboBox {
    background-color: %sidebar%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 14px;
    min-height: 20px;
}

QComboBox:hover {
    border: 1px solid %text_dim%;
}

QComboBox:focus {
    border: 1px solid %button%;
}

QComboBox:disabled {
    background-color: #2A2A2A;
    color: #666666;
    border: 1px solid #333333;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    background: transparent;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid %text_dim%;
    width: 0;
    height: 0;
    margin-right: 6px;
}

QComboBox::down-arrow:hover {
    border-top: 5px solid %text%;
}

QComboBox QAbstractItemView {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: %button%;
    selection-color: white;
}

QComboBox QAbstractItemView::item {
    background-color: %card%;
    color: %text%;
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 22px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: %hover%;
    color: white;
}

QComboBox QAbstractItemView::item:selected {
    background-color: %button%;
    color: white;
}

/* =========================================================
   QCompleter
   ========================================================= */
QCompleter QAbstractItemView,
QListView {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: %button%;
    selection-color: white;
}

QCompleter QAbstractItemView::item,
QListView::item {
    background-color: %card%;
    color: %text%;
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 22px;
}

QCompleter QAbstractItemView::item:hover,
QListView::item:hover {
    background-color: %hover%;
    color: white;
}

QCompleter QAbstractItemView::item:selected,
QListView::item:selected {
    background-color: %button%;
    color: white;
}

/* =========================================================
   QDateEdit
   ========================================================= */
QDateEdit {
    background-color: %sidebar%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 14px;
}
QDateEdit:hover {
    border: 1px solid %text_dim%;
}
QDateEdit:focus {
    border: 1px solid %button%;
}
QDateEdit::up-button, QDateEdit::down-button {
    width: 0;
    height: 0;
    border: none;
    background: transparent;
}
QDateEdit::drop-down {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 100%;
    border: none;
    background: transparent;
}
QDateEdit::down-arrow {
    image: none;
    width: 0;
    height: 0;
}

/* =========================================================
   QCalendarWidget
   ========================================================= */
QCalendarWidget QWidget {
    background-color: %card%;
    color: %text%;
}
QCalendarWidget QAbstractItemView:enabled {
    background-color: %card%;
    color: %text%;
    selection-background-color: %button%;
    selection-color: white;
    outline: none;
}
QCalendarWidget QAbstractItemView:disabled {
    color: #555555;
}
QCalendarWidget QToolButton {
    background-color: %sidebar%;
    color: %text%;
    border: none;
    padding: 4px 8px;
    font-size: 13px;
}
QCalendarWidget QToolButton:hover {
    background-color: %hover%;
    color: white;
}
QCalendarWidget QMenu {
    background-color: %sidebar%;
    color: %text%;
    border: 1px solid %border%;
}
QCalendarWidget QMenu::item:selected {
    background-color: %button%;
    color: white;
}
QCalendarWidget QSpinBox {
    background-color: %sidebar%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 4px;
    padding: 2px 6px;
}
QCalendarWidget QSpinBox::up-button,
QCalendarWidget QSpinBox::down-button {
    background-color: %sidebar%;
    border: none;
    width: 14px;
}
QCalendarWidget QSpinBox::up-button:hover,
QCalendarWidget QSpinBox::down-button:hover {
    background-color: %hover%;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: %sidebar%;
}
QCalendarWidget QWidget#qt_calendar_calendarview {
    background-color: %card%;
}

/* =========================================================
   QTreeWidget (оглавление GuideTab)
   ========================================================= */
QTreeWidget {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    font-size: 14px;
}

QTreeWidget::item {
    padding: 8px 6px;
    border-radius: 4px;
    margin-bottom: 2px;
}

QTreeWidget::item:hover {
    background-color: %sidebar%;
}

QTreeWidget::item:selected {
    background-color: %button%;
    color: white;
}

QTreeWidget::item:disabled {
    color: %text_dim%;
}

QTreeWidget::branch {
    background: transparent;
}

QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {
    background: transparent;
}

QTreeWidget::branch:open:has-children:!has-siblings,
QTreeWidget::branch:open:has-children:has-siblings {
    background: transparent;
}

QHeaderView::section {
    background-color: %card%;
    color: %text_dim%;
    border: none;
    padding: 4px;
}

/* =========================================================
   QTextBrowser (фолбэк для GuideTab)
   ========================================================= */
QTextBrowser {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 8px;
    padding: 20px;
    selection-background-color: %button%;
    selection-color: white;
}

QTextBrowser QScrollBar:vertical {
    border: none;
    background: %card%;
    width: 10px;
    margin: 0px;
}

QTextBrowser QScrollBar::handle:vertical {
    background: %border%;
    min-height: 20px;
    border-radius: 5px;
}

QTextBrowser QScrollBar::handle:vertical:hover {
    background: %text_dim%;
}

QTextBrowser QScrollBar::add-line:vertical,
QTextBrowser QScrollBar::sub-line:vertical {
    height: 0px;
}
/* =========================================================
   Системные диалоги и меню — тёмные
   ========================================================= */
QDialog, QMessageBox, QFileDialog, QInputDialog {
    background-color: %bg%;
    color: %text%;
}

QMessageBox QLabel, QFileDialog QLabel, QInputDialog QLabel {
    color: %text%;
    background-color: transparent;
}

QMessageBox QPushButton, QFileDialog QPushButton, QInputDialog QPushButton {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 6px 18px;
    min-width: 80px;
}

QMessageBox QPushButton:hover,
QFileDialog QPushButton:hover,
QInputDialog QPushButton:hover {
    background-color: %button%;
    color: #FFFFFF;
    border-color: %button%;
}

QFileDialog QListView, QFileDialog QTreeView, QFileDialog QComboBox,
QInputDialog QLineEdit, QInputDialog QComboBox {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: %button%;
    selection-color: #FFFFFF;
    outline: none;
}

QFileDialog QHeaderView::section {
    background-color: %sidebar%;
    color: %text_dim%;
    border: none;
    border-bottom: 1px solid %border%;
    padding: 6px 8px;
}

QMenu {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 6px;
}

QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: %button%;
    color: #FFFFFF;
}

QMenu::separator {
    height: 1px;
    background: %border%;
    margin: 4px 8px;
}

QToolTip {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 4px;
    padding: 6px 8px;
}

QComboBox {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 6px 10px;
}

QComboBox QAbstractItemView {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    selection-background-color: %button%;
    selection-color: #FFFFFF;
    outline: none;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit, QTimeEdit {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: %button%;
    selection-color: #FFFFFF;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QDateTimeEdit:focus, QTimeEdit:focus {
    border: 1px solid %button%;
}

QCalendarWidget QWidget {
    background-color: %card%;
    color: %text%;
}

QCheckBox, QRadioButton {
    color: %text%;
    background-color: transparent;
    spacing: 8px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid %border%;
    border-radius: 3px;
    background-color: %card%;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: %button%;
    border-color: %button%;
}

QTabWidget::pane {
    border: 1px solid %border%;
    border-radius: 8px;
    background-color: %card%;
}

QTabBar::tab {
    background-color: %sidebar%;
    color: %text_dim%;
    border: 1px solid %border%;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: %card%;
    color: %text%;
}

QProgressBar {
    background-color: %bg%;
    border: 1px solid %border%;
    border-radius: 6px;
    text-align: center;
    color: %text%;
}

QProgressBar::chunk {
    background-color: %button%;
    border-radius: 5px;
}

"""


# =========================================================
# СБОРКА QSS С ПОДСТАНОВКОЙ ЦВЕТОВ
# =========================================================
def build_qss(colors=None):
    """Собирает QSS из шаблона, подставляя цвета."""
    if colors is None:
        from config import COLORS as colors

    qss = QSS_TEMPLATE
    for key, value in colors.items():
        qss = qss.replace(f"%{key}%", str(value))
    return qss

# =========================================================
# ТЁМНАЯ ПАЛИТРА ПРИЛОЖЕНИЯ
# =========================================================
def build_dark_palette(colors=None):
    """Тёмная QPalette для всего приложения.

    QSS красит только Qt-виджеты, а системные окна (QFileDialog,
    QInputDialog, QMessageBox, меню, подсказки) берут цвета из палитры.
    Без неё они остаются светлыми — отсюда белые шапки уведомлений
    и белые списки в проводнике выбора файла.
    """
    from PyQt6.QtGui import QPalette, QColor, QBrush

    if colors is None:
        from config import get_config
        colors = get_config().COLORS

    bg = QColor(colors.get("bg", "#1B1B1B"))
    sidebar = QColor(colors.get("sidebar", "#2A2A2A"))
    card = QColor(colors.get("card", "#222222"))
    text = QColor(colors.get("text", "#E0E0E0"))
    text_dim = QColor(colors.get("text_dim", "#A0A0A0"))
    button = QColor(colors.get("button", "#D42626"))
    hover = QColor(colors.get("hover", "#B71C1C"))
    border = QColor(colors.get("border", "#333333"))
    disabled = QColor("#6E6E6E")

    palette = QPalette()

    # Основные окна
    palette.setColor(QPalette.ColorRole.Window, bg)
    palette.setColor(QPalette.ColorRole.WindowText, text)

    # Поля ввода, списки, таблицы, деревья
    palette.setColor(QPalette.ColorRole.Base, card)
    palette.setColor(QPalette.ColorRole.AlternateBase, sidebar)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.PlaceholderText, text_dim)

    # Кнопки
    palette.setColor(QPalette.ColorRole.Button, card)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))

    # Подсказки
    palette.setColor(QPalette.ColorRole.ToolTipBase, card)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)

    # Выделение
    palette.setColor(QPalette.ColorRole.Highlight, button)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))

    # Ссылки
    palette.setColor(QPalette.ColorRole.Link, button)
    palette.setColor(QPalette.ColorRole.LinkVisited, hover)

    # Неактивные элементы
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
        palette.setColor(QPalette.ColorGroup.Inactive, role, text)

    for role in (
        QPalette.ColorRole.Window,
        QPalette.ColorRole.Base,
        QPalette.ColorRole.Button,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, bg)
        palette.setColor(QPalette.ColorGroup.Inactive, role, bg)

    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Highlight,
        QColor("#4A4A4A"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.HighlightedText,
        disabled,
    )

    return palette


def apply_dark_theme(app, colors=None):
    """Ставит палитру и QSS. Вызывать сразу после создания QApplication."""
    app.setPalette(build_dark_palette(colors))
    app.setStyleSheet(build_qss(colors))
