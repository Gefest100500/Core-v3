# ui/frames/dashboard_frame.py
"""
Дашборд инвентаризации ГМ.

Открывается из Архива (is_embedded=True) по выбранной инвентаризации.
Работает на ФИНАЛЬНЫХ письмах: дневные больше не собираются.

Что показывает (из final_details парсера):
- шапку: ГМ, формат, вариант, даты, длительность, период, комиссия;
- итоги: сумма с РМ и МЦ / без РМ и МЦ;
- модуль отклонений с выделенной зоной;
- круговой график: списания vs инвентаризации в структуре отклонений;
- финансы за период: продажи, отклонения по списаниям и инвентаризациям;
- кассу ГК: план, факт, результат сверки;
- качество технологий товародвижения.

Экспорт: «Сохранить как PNG» снимает весь дашборд.
"""
import os
from datetime import datetime

from PyQt6.QtCore import Qt, QSize, QRectF, QSettings
from PyQt6.QtGui import (
    QColor, QBrush, QPen, QFont, QPainter, QFontMetrics, QPixmap,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QSizePolicy, QGridLayout,
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import SecondaryButton
from ui.icons import get_icon_simple
from core.email_analytics import get_zone_color, summary
from utils.logger import log

SETTINGS_ORG = "SilchenkoAleksey"
SETTINGS_APP = "CoreV3"

CARD_BG = "#222222"
CARD_BORDER = "#333333"
TEXT = "#E0E0E0"
TEXT_DIM = "#A0A0A0"
ACCENT = "#D42626"
SUCCESS = "#4CAF50"
ERROR = "#FF5252"
WARN = "#FFD700"


def _fmt_money(v) -> str:
    """1 622 598,15 ₽"""
    if v is None:
        return "—"
    try:
        s = f"{float(v):,.2f}".replace(",", " ").replace(".", ",")
        return f"{s} ₽"
    except (TypeError, ValueError):
        return "—"


def _fmt_int(v) -> str:
    """1 873 609 838"""
    if v is None:
        return "—"
    try:
        return f"{int(round(float(v))):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def _fmt_percent(v) -> str:
    if v is None:
        return ""
    try:
        return f"{float(v):.2f} %".replace(".", ",")
    except (TypeError, ValueError):
        return ""


def _sign_color(sign_type: str) -> str:
    """Цвет по типу: недостача — красный, излишек — зелёный."""
    s = (sign_type or "").lower()
    if s.startswith("излиш"):
        return SUCCESS
    if s.startswith("недостач"):
        return ERROR
    return TEXT


class PieChart(QWidget):
    """Круговой график с легендой-списком справа."""

    def __init__(self, data=None, parent=None, center_text=None):
        super().__init__(parent)
        self._data = data or []          # [(label, value, color)]
        self._center_text = center_text
        self.setMinimumSize(240, 240)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def set_data(self, data, center_text=None):
        self._data = data or []
        self._center_text = center_text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._data:
            painter.setPen(QColor(TEXT_DIM))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет данных"
            )
            painter.end()
            return

        total = sum(abs(v) for _, v, _ in self._data)
        if total <= 0:
            painter.setPen(QColor(TEXT_DIM))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет данных"
            )
            painter.end()
            return

        side = min(self.width(), self.height()) - 24
        if side < 120:
            side = 120
        x = (self.width() - side) // 2
        y = (self.height() - side) // 2
        rect = QRectF(x, y, side, side)

        start_angle = 90 * 16
        for _label, value, color in self._data:
            abs_v = abs(value)
            if abs_v <= 0:
                continue
            span = int(360 * 16 * abs_v / total)
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(QPen(QColor(CARD_BG), 2))
            painter.drawPie(rect, start_angle, -span)
            start_angle -= span

        # Внутренний круг — «пончик»
        inner_side = int(side * 0.58)
        inner_x = x + (side - inner_side) // 2
        inner_y = y + (side - inner_side) // 2
        painter.setBrush(QBrush(QColor(CARD_BG)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(inner_x, inner_y, inner_side, inner_side))

        if self._center_text:
            painter.setPen(QColor(TEXT))
            font = QFont("Segoe UI", 12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                QRectF(inner_x, inner_y, inner_side, inner_side),
                Qt.AlignmentFlag.AlignCenter,
                self._center_text,
            )

        painter.end()


class HBar(QFrame):
    """Горизонтальный бар с подписью и значением."""

    LABEL_WIDTH = 260
    VALUE_WIDTH = 150

    def __init__(self, label, value, max_value, color=None,
                 value_text=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.setStyleSheet("QFrame { background: transparent; }")

        if color is None:
            color = ACCENT

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._full_label = str(label)
        self._label = QLabel(self)
        self._label.setFixedWidth(self.LABEL_WIDTH)
        self._label.setStyleSheet(f"color: {TEXT}; background: transparent;")
        self._label.setToolTip(self._full_label)
        layout.addWidget(self._label)

        bar_area = QFrame()
        bar_area.setFixedHeight(10)
        bar_area.setStyleSheet("QFrame { background: transparent; }")
        bar_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self.bar = QFrame(bar_area)
        self.bar.setStyleSheet(
            f"QFrame {{ background-color: {color}; border-radius: 5px; }}"
        )

        self._bar_area = bar_area
        self._max_value = max_value
        self._value = value
        layout.addWidget(bar_area, 1)

        text_val = value_text if value_text is not None else str(value)
        val_label = QLabel(text_val)
        val_label.setFixedWidth(self.VALUE_WIDTH)
        val_label.setStyleSheet(
            f"color: {TEXT}; font-family: Consolas; background: transparent;"
        )
        val_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(val_label)

        self._update_label_elide()

    def _update_label_elide(self):
        try:
            fm = QFontMetrics(self._label.font())
            elided = fm.elidedText(
                self._full_label,
                Qt.TextElideMode.ElideRight,
                self.LABEL_WIDTH - 4,
            )
            self._label.setText(elided)
        except Exception:
            self._label.setText(self._full_label)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_bar()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_bar()
        self._update_label_elide()

    def _update_bar(self):
        try:
            cw = self._bar_area.width()
            h = self._bar_area.height()
            if self._max_value > 0:
                w = int(cw * self._value / self._max_value)
            else:
                w = 0
            self.bar.setGeometry(0, 0, max(0, w), h)
        except Exception:
            pass


class DashboardFrame(BaseFrame):
    TITLE = "Дашборд"

    def __init__(self, parent, name=None,
                 initial_gm_code: str = "",
                 is_embedded: bool = False):
        self._initial_gm_code = initial_gm_code or ""
        self._is_embedded = bool(is_embedded)

        super().__init__(parent, name)
        self.scroll_content = None
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        self._setup_ui()

        if self._initial_gm_code:
            self._gm_code = self._initial_gm_code
        else:
            self._gm_code = ""

        self.refresh()

    # =========================================================
    # UI КАРКАС
    # =========================================================
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 8) if self._is_embedded \
            else root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        top_row.addStretch()

        self.btn_export = SecondaryButton(
            "Сохранить как PNG",
            on_click=self._export_png,
            parent=self,
        )
        self.btn_export.setMinimumWidth(200)
        self.btn_export.setMinimumHeight(40)
        export_icon = get_icon_simple("download", color=TEXT, size=16)
        if not export_icon.isNull():
            self.btn_export.setIcon(export_icon)
            self.btn_export.setIconSize(QSize(16, 16))
        top_row.addWidget(self.btn_export)

        root.addLayout(top_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        content = QWidget()
        content.setStyleSheet("QWidget { background: transparent; }")
        self.main_layout = QVBoxLayout(content)
        self.main_layout.setContentsMargins(0, 0, 20, 0)
        self.main_layout.setSpacing(18)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.scroll_content = content

    # =========================================================
    # ОБЩИЕ ЭЛЕМЕНТЫ
    # =========================================================
    def _card(self, min_height: int = 0) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(self.scroll_content)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 10px;
            }}
        """)
        if min_height:
            card.setMinimumHeight(min_height)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        return card, lay

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: bold; "
            f"letter-spacing: 1px; background: transparent;"
        )
        return lbl

    def _stat(self, label: str, value: str, color: str = TEXT,
              sub: str = "") -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: transparent; }")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
        )
        lay.addWidget(lbl)

        val = QLabel(value)
        val.setStyleSheet(
            f"color: {color}; font-size: 20px; font-weight: bold; "
            f"background: transparent;"
        )
        lay.addWidget(val)

        if sub:
            s = QLabel(sub)
            s.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
            )
            lay.addWidget(s)

        return frame

    def _clear(self):
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            child = item.layout()
            if child is not None:
                while child.count():
                    sub = child.takeAt(0)
                    sw = sub.widget()
                    if sw is not None:
                        sw.deleteLater()

    # =========================================================
    # ПОСТРОЕНИЕ
    # =========================================================
    def _refresh_all(self):
        self._clear()

        gm_code = getattr(self, "_gm_code", "") or self._initial_gm_code

        if not gm_code:
            hint = QLabel("Выберите инвентаризацию в Архиве")
            hint.setFont(self.FONTS['title'])
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(
                f"color: {TEXT_DIM}; padding: 60px 20px;"
            )
            self.main_layout.addWidget(hint)
            self.main_layout.addStretch()
            return

        try:
            s = summary(gm_code)
        except Exception as e:
            log.exception(f"DashboardFrame: ошибка аналитики: {e}")
            err = QLabel(f"Ошибка загрузки данных: {e}")
            err.setStyleSheet(f"color: {ERROR}; padding: 20px;")
            self.main_layout.addWidget(err)
            return

        if s.get("emails_count", 0) == 0 and not s.get("gm_code"):
            t = QLabel("Нет данных по этому ГМ")
            t.setFont(self.FONTS['title'])
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setStyleSheet("padding: 40px;")
            self.main_layout.addWidget(t)

            hint = QLabel(
                "Соберите письма: «Забрать информацию» в Архиве."
            )
            hint.setStyleSheet(f"color: {TEXT_DIM};")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.main_layout.addWidget(hint)
            self.main_layout.addStretch()
            return

        self._build_header(s)
        self._build_totals(s)
        self._build_breakdown(s)
        self._build_finance(s)
        self._build_cash_quality(s)

        self.main_layout.addStretch()

    # ---------------------------------------------------------
    def _build_header(self, s: dict):
        card, lay = self._card()

        title = QLabel(f"ГМ {s.get('gm_code', '')} — {s.get('gm_name', '')}")
        title.setStyleSheet(
            f"color: {TEXT}; font-size: 22px; font-weight: bold; "
            f"background: transparent;"
        )
        lay.addWidget(title)

        fd = s.get("final_details") or {}

        meta_parts = []
        if s.get("start_date") and s.get("end_date"):
            meta_parts.append(f"{s['start_date']} — {s['end_date']}")
        if s.get("duration_text"):
            meta_parts.append(s["duration_text"])
        elif s.get("duration_days"):
            meta_parts.append(f"{s['duration_days']} суток")
        if s.get("variant"):
            meta_parts.append(f"Вариант {s['variant']}")
        if fd.get("gm_format"):
            meta_parts.append(f"Формат: {fd['gm_format']}")
        if fd.get("last_period"):
            meta_parts.append(f"Учётный период: {fd['last_period']}")

        if meta_parts:
            meta = QLabel("  ·  ".join(meta_parts))
            meta.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 13px; background: transparent;"
            )
            meta.setWordWrap(True)
            lay.addWidget(meta)

        commission = fd.get("commission") or []
        if commission:
            lay.addSpacing(6)

            ct = QLabel("СОСТАВ КОМИССИИ")
            ct.setStyleSheet(
                f"color: {ACCENT}; font-size: 10px; font-weight: bold; "
                f"letter-spacing: 1px; background: transparent;"
            )
            lay.addWidget(ct)

            for person in commission:
                name = person.get("name", "")
                role = person.get("role", "")
                line = f"{name}" + (f"  —  {role}" if role else "")
                p = QLabel("• " + line)
                p.setStyleSheet(
                    f"color: {TEXT}; font-size: 13px; background: transparent;"
                )
                lay.addWidget(p)

        self.main_layout.addWidget(card)

    # ---------------------------------------------------------
    def _build_totals(self, s: dict):
        card, lay = self._card()
        lay.addWidget(self._section_title("ИТОГИ ПОЛНОЙ ИНВЕНТАРИЗАЦИИ"))

        row = QHBoxLayout()
        row.setSpacing(24)

        ft = s.get("final_totals") or {}
        with_rm = ft.get("with_rm") or {}
        without_rm = ft.get("without_rm") or {}

        row.addWidget(self._stat(
            "С РМ и МЦ",
            _fmt_money(with_rm.get("amount")),
            _sign_color(with_rm.get("type")),
            (with_rm.get("type") or "").capitalize(),
        ), 1)

        row.addWidget(self._stat(
            "Без РМ и МЦ",
            _fmt_money(without_rm.get("amount")),
            _sign_color(without_rm.get("type")),
            (without_rm.get("type") or "").capitalize(),
        ), 1)

        lay.addLayout(row)
        self.main_layout.addWidget(card)

    # ---------------------------------------------------------
    def _build_breakdown(self, s: dict):
        """Модуль отклонений + зоны + круговой график финансирования."""
        fd = s.get("final_details") or {}
        module = fd.get("module_deviation") or {}
        zones = fd.get("zones") or []
        finance = fd.get("finance") or {}

        if not module and not zones:
            return

        card, lay = self._card()
        lay.addWidget(self._section_title("СТРУКТУРА ОТКЛОНЕНИЙ"))

        module_amount = module.get("amount") or 0
        zone_amount = module.get("zone_amount") or 0
        zone_name = module.get("zone") or ""

        # Информационная строка
        if module_amount:
            info = QLabel(
                f"Модуль суммы отклонений: {_fmt_money(module_amount)}"
            )
            info.setStyleSheet(
                f"color: {TEXT}; font-size: 14px; background: transparent;"
            )
            lay.addWidget(info)

        # Бары
        bars_data = []
        if module_amount:
            bars_data.append(("Модуль отклонений", module_amount, ACCENT))
        for z in zones:
            bars_data.append((
                z.get("name", ""),
                abs(z.get("amount") or 0),
                get_zone_color(z.get("name", "")),
            ))
        if zone_name and zone_amount:
            bars_data.append((zone_name, abs(zone_amount), get_zone_color(zone_name)))

        max_val = max((v for _, v, _ in bars_data), default=0)

        for label, value, color in bars_data:
            lay.addWidget(HBar(
                label, value, max_val, color=color,
                value_text=_fmt_money(value),
            ))

        # Круговой: списания vs инвентаризации
        writeoff = (finance.get("writeoff") or {}).get("amount") or 0
        inventory = (finance.get("inventory") or {}).get("amount") or 0

        if writeoff or inventory:
            lay.addSpacing(8)

            pie_row = QHBoxLayout()
            pie_row.setSpacing(20)

            pie_data = []
            if writeoff:
                pie_data.append(("Списания", writeoff, "#E57373"))
            if inventory:
                pie_data.append(("Инвентаризации", inventory, ACCENT))

            total_dev = writeoff + inventory
            pie = PieChart(
                pie_data,
                center_text=_fmt_int(total_dev),
            )
            pie.setMinimumHeight(260)
            pie_row.addWidget(pie, 1)

            # Легенда
            legend = QFrame()
            legend.setStyleSheet("QFrame { background: transparent; }")
            leg_lay = QVBoxLayout(legend)
            leg_lay.setContentsMargins(0, 0, 0, 0)
            leg_lay.setSpacing(8)
            leg_lay.addStretch()

            for label, value, color in pie_data:
                lrow = QHBoxLayout()
                dot = QLabel("●")
                dot.setStyleSheet(
                    f"color: {color}; font-size: 16px; background: transparent;"
                )
                lrow.addWidget(dot)

                lname = QLabel(label)
                lname.setStyleSheet(
                    f"color: {TEXT}; font-size: 13px; background: transparent;"
                )
                lrow.addWidget(lname)
                lrow.addStretch()

                pct = (value / total_dev * 100) if total_dev else 0
                lval = QLabel(f"{_fmt_money(value)}  ({pct:.1f}%)")
                lval.setStyleSheet(
                    f"color: {TEXT_DIM}; font-size: 12px; "
                    f"font-family: Consolas; background: transparent;"
                )
                lrow.addWidget(lval)

                wrap = QWidget()
                wrap.setStyleSheet("QWidget { background: transparent; }")
                wrap.setLayout(lrow)
                leg_lay.addWidget(wrap)

            leg_lay.addStretch()
            pie_row.addWidget(legend, 1)

            pie_wrap = QWidget()
            pie_wrap.setStyleSheet("QWidget { background: transparent; }")
            pie_wrap.setLayout(pie_row)
            lay.addWidget(pie_wrap)

        self.main_layout.addWidget(card)

    # ---------------------------------------------------------
    def _build_finance(self, s: dict):
        fd = s.get("final_details") or {}
        finance = fd.get("finance") or {}

        sales = finance.get("sales")
        writeoff = finance.get("writeoff") or {}
        inventory = finance.get("inventory") or {}
        total = finance.get("total") or {}

        if not any([sales, writeoff.get("amount"), inventory.get("amount"),
                    total.get("amount")]):
            return

        card, lay = self._card()
        lay.addWidget(self._section_title("ФИНАНСЫ ЗА УЧЁТНЫЙ ПЕРИОД"))

        if sales:
            sales_lbl = QLabel(f"Продажи за период: {_fmt_money(sales)}")
            sales_lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 15px; "
                f"font-weight: bold; background: transparent;"
            )
            lay.addWidget(sales_lbl)
            lay.addSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)

        def add_cell(row, col, label, value, color=TEXT, sub=""):
            cell = self._stat(label, value, color, sub)
            grid.addWidget(cell, row, col)

        if writeoff.get("amount") is not None:
            add_cell(
                0, 0,
                "Отклонения по списаниям",
                _fmt_money(writeoff["amount"]),
                ERROR,
                _fmt_percent(writeoff.get("percent")) + " от продаж",
            )

        if inventory.get("amount") is not None:
            add_cell(
                0, 1,
                "Отклонения по инвентаризациям",
                _fmt_money(inventory["amount"]),
                WARN,
                _fmt_percent(inventory.get("percent")) + " от продаж",
            )

        if total.get("amount") is not None:
            add_cell(
                1, 0,
                "Итого отклонений за период",
                _fmt_money(total["amount"]),
                ACCENT,
                _fmt_percent(total.get("percent")) + " от продаж",
            )

        lay.addLayout(grid)
        self.main_layout.addWidget(card)

    # ---------------------------------------------------------
    def _build_cash_quality(self, s: dict):
        fd = s.get("final_details") or {}
        cash = fd.get("cash") or {}
        quality = fd.get("quality") or {}

        plan = cash.get("plan")
        fact = cash.get("fact")
        result = cash.get("result") or ""
        qpct = quality.get("percent")
        qlevel = quality.get("level") or ""

        if plan is None and fact is None and qpct is None:
            return

        row = QHBoxLayout()
        row.setSpacing(18)

        # Касса
        if plan is not None or fact is not None:
            card, lay = self._card()
            lay.addWidget(self._section_title("КАССА ГК"))

            r = QHBoxLayout()
            r.setSpacing(24)
            r.addWidget(self._stat(
                "По учёту", _fmt_money(plan), TEXT
            ), 1)
            r.addWidget(self._stat(
                "По факту", _fmt_money(fact), TEXT
            ), 1)
            lay.addLayout(r)

            if result:
                res = QLabel(result)
                res.setStyleSheet(
                    f"color: {SUCCESS if 'не выявл' in result.lower() else ERROR}; "
                    f"font-size: 13px; background: transparent;"
                )
                lay.addWidget(res)

            row.addWidget(card, 1)

        # Качество
        if qpct is not None:
            card, lay = self._card()
            lay.addWidget(self._section_title("КАЧЕСТВО ТЕХНОЛОГИЙ"))

            lay.addWidget(self._stat(
                "Товародвижение ГМ",
                f"{qpct:.1f} %".replace(".", ","),
                SUCCESS if qpct >= 80 else WARN,
                qlevel.capitalize() if qlevel else "",
            ))

            row.addWidget(card, 1)

        wrap = QWidget()
        wrap.setStyleSheet("QWidget { background: transparent; }")
        wrap.setLayout(row)
        self.main_layout.addWidget(wrap)

    # =========================================================
    # ЭКСПОРТ
    # =========================================================
    def _export_png(self):
        try:
            from config import FOLDERS
            out_dir = os.path.join(
                FOLDERS.get("info", ""), "Дашборды"
            )
            os.makedirs(out_dir, exist_ok=True)

            date_str = datetime.now().strftime("%Y%m%d_%H%M")
            gm = getattr(self, "_gm_code", "") or "noGM"
            path = os.path.join(out_dir, f"dashboard_{gm}_{date_str}.png")

            target = self.scroll_content
            if target is None:
                self.show_error("Ошибка", "Нечего экспортировать.")
                return

            pixmap: QPixmap = target.grab()
            if not pixmap.save(path, "PNG"):
                self.show_error("Ошибка", f"Не удалось сохранить PNG:\n{path}")
                return

            self.set_status(f"Сохранено: {path}", SUCCESS)
            self.show_success("Готово", f"Дашборд сохранён:\n{path}")

        except Exception as e:
            log.exception("DashboardFrame: ошибка экспорта PNG")
            self.show_error("Ошибка", f"Не удалось сохранить PNG:\n{e}")

    # =========================================================
    # ХУКИ
    # =========================================================
    def refresh(self):
        self._refresh_all()

    def on_hide(self):
        pass

    def on_close(self):
        pass
