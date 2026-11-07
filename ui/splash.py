# ui/splash.py
"""
Заставка (SplashScreen) для Core V3.0.
"""
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QFont, QMouseEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame, 
    QGraphicsOpacityEffect, QPushButton
)

from ui.icons import get_icon_simple


class SplashScreen(QWidget):
    """Заставка при старте приложения (во весь экран)."""

    def __init__(self, colors, fonts):
        super().__init__()
        self._colors = colors
        self._fonts = fonts

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._drag_pos = None

        self._setup_ui()
        self.showFullScreen()

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        bg = self._colors.get("bg", "#1B1B1B")
        text = self._colors.get("text", "#E0E0E0")
        text_dim = self._colors.get("text_dim", "#A0A0A0")
        accent_light = "#888888"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg};
            }}
            QFrame#SplashBorder {{
                background-color: {bg};
                border: none;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        frame = QFrame(self)
        frame.setObjectName("SplashBorder")
        outer.addWidget(frame)

        # Главный вертикальный слой
        main_layout = QVBoxLayout(frame)
        main_layout.setContentsMargins(20, 20, 20, 80) # Отступы по краям
        main_layout.setSpacing(20)

        # --- ВЕРХНЯЯ ПАНЕЛЬ С КНОПКОЙ ---
        top_bar = QHBoxLayout()
        top_bar.addStretch() # Прижимаем всё вправо
        
        self.btn_minimize = QPushButton("—", frame)
        self.btn_minimize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minimize.setFixedSize(30, 30)
        self.btn_minimize.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {text_dim};
                border: none;
                font-size: 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {text};
                background-color: #333333;
                border-radius: 4px;
            }}
        """)
        self.btn_minimize.clicked.connect(self.showMinimized)
        top_bar.addWidget(self.btn_minimize)
        
        main_layout.addLayout(top_bar)

        # --- ЦЕНТРАЛЬНЫЙ БЛОК (Логотип, текст, полоска) ---
        center_layout = QVBoxLayout()
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.setSpacing(20)

        logo_icon = get_icon_simple("home", color=accent_light, size=96)
        logo_label = QLabel(frame)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if not logo_icon.isNull():
            logo_label.setPixmap(logo_icon.pixmap(96, 96))
        center_layout.addWidget(logo_label)

        title = QLabel("CORE", frame)
        title.setFont(QFont("Segoe UI", 48, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {accent_light};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(title)

        subtitle = QLabel("Корпоративный аудит", frame)
        subtitle.setFont(QFont("Segoe UI", 16))
        subtitle.setStyleSheet(f"color: {text_dim};")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(subtitle)

        center_layout.addSpacing(40)

        self.status_label = QLabel("Инициализация...", frame)
        self.status_label.setFont(QFont("Segoe UI", 13))
        self.status_label.setStyleSheet(f"color: {text};")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.status_label)

        # Прогресс-бар
        progress_container = QVBoxLayout()
        progress_container.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress = QProgressBar(frame)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setFixedWidth(400)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: #2A2A2A;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {accent_light};
                border-radius: 2px;
            }}
        """)
        progress_container.addWidget(self.progress)
        center_layout.addLayout(progress_container)

        # Добавляем центральный блок в главный слой (он растянется)
        main_layout.addLayout(center_layout, 1)

    # =========================================================
    # ПУБЛИЧНЫЕ МЕТОДЫ
    # =========================================================
    def set_status(self, text: str, is_loading: bool = False):
        self.status_label.setText(text)
        
        if is_loading:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)

    def set_progress(self, value: int):
        if self.progress.maximum() == 0:
            return
        self.progress.setValue(max(0, min(100, value)))

    def fade_out_and_close(self, on_finished=None):
        """Плавно скрывает заставку и закрывает её."""
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(400)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _done():
            self.close()
            self.deleteLater()
            if on_finished:
                on_finished()

        self._anim.finished.connect(_done)
        self._anim.start()

    # =========================================================
    # ПЕРЕТАСКИВАНИЕ
    # =========================================================
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        event.accept()