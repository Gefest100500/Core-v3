# ui/frames/dashboard_frame.py
"""
Дашборд инвентаризации ГМ.

Открывается из Архива (is_embedded=True) по выбранной инвентаризации.
Строится на ВСЕХ письмах ГМ: дневные дают зоны, динамику и часы
ревизоров, финальное — итоговые суммы и финансы.

Правило знака в Core:
    сумма >= 0  — НЕДОСТАЧА
    сумма <  0  — ИЗЛИШЕК

Экспорт: «Сохранить как PNG» снимает весь дашборд.
"""
import os
from datetime import datetime

from PyQt6.QtCore import Qt, QSize, QRectF, QSettings, QPointF
from PyQt6.QtGui import (
    QColor, QBrush, QPen, QFont, QPainter, QFontMetrics, QPixmap, QPolygonF,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QSizePolicy, QGridLayout,
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import SecondaryButton
from ui.icons import get_icon_simple
from core.email_analytics import (
    summary, top_zones, top_other_events, time_total, summary_history,
    get_zone_color, ZONES_CANONICAL,
)
from utils.logger import log

SETTINGS_ORG = "SilchenkoAleksey"
SETTINGS_APP = "CoreV3"

CARD_BG = "#222222"
CARD_BORDER = "#333333"
BG = "#1B1B1B"
TEXT = "#E0E0E0"
TEXT_DIM = "#A0A0A0"
ACCENT = "#D42626"
SUCCESS = "#4CAF50"
ERROR = "#FF5252"
WARN = "#FFD700"


# =========================================================
# ФОРМАТИРОВАНИЕ
# =========================================================
def _fmt_money(v, sign: bool = True) -> str:
    """1 622 598,15 ₽ — знак минус только для излишка."""
    if v is None:
        return "—"
    try:
        val = float(v)
    except (TypeError, ValueError):
        return "—"
    prefix = ""
    if sign and val < 0:
        prefix = "−"
    s = f"{abs(val):,.2f}".replace(",", " ").replace(".", ",")
    return f"{prefix}{s} ₽"


def _fmt_int(v) -> str:
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


def _type_word(v) -> str:
    """Слово по знаку: >= 0 — недостача, < 0 — излишек."""
    try:
        return "излишек" if float(v) < 0 else "недостача"
    except (TypeError, ValueError):
        return ""


def _type_color(v) -> str:
    """Цвет по знаку."""
    try:
        return SUCCESS if float(v) < 0 else ERROR
    except (TypeError, ValueError):
        return TEXT


# =========================================================
# ГРАФИКИ
# =========================================================
class DonutChart(QWidget):
    """Круговой график по зонам с подписями-выносками."""

    def __init__(self, data=None, parent=None, center_text="", center_sub=""):
        super().__init__(parent)
        self._data = data or []        # [(label, value, color)]
        self._center_text = center_text
        self._center_sub = center_sub
        self.setMinimumSize(360, 360)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def set_data(self, data, center_text="", center_sub=""):
        self._data = data or []
        self._center_text = center_text
        self._center_sub = center_sub
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        items = [(l, abs(v), c) for l, v, c in self._data if abs(v) > 0]
        if not items:
            p.setPen(QColor(TEXT_DIM))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет данных")
            p.end()
            return

        total = sum(v for _, v, _ in items)

        side = min(self.width(), self.height()) - 24
        if side < 160:
            side = 160
        x = (self.width() - side) // 2
        y = (self.height() - side) // 2
        rect = QRectF(x, y, side, side)

        # сектора
        start = 90 * 16
        for _label, value, color in items:
            span = int(360 * 16 * value / total)
            p.setBrush(QBrush(QColor(color)))
            p.setPen(QPen(QColor(CARD_BG), 2))
            p.drawPie(rect, start, -span)
            start -= span

        # «пончик»
        inner = int(side * 0.56)
        ix = x + (side - inner) // 2
        iy = y + (side - inner) // 2
        p.setBrush(QBrush(QColor(CARD_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(ix, iy, inner, inner))

        # центр
        if self._center_text:
            p.setPen(QColor(TEXT))
            f = QFont("Segoe UI", 13)
            f.setBold(True)
            p.setFont(f)
            top_h = inner // 2
            p.drawText(
                QRectF(ix, iy + inner * 0.18, inner, top_h),
                Qt.AlignmentFlag.AlignCenter,
                self._center_text,
            )
            if self._center_sub:
                p.setPen(QColor(TEXT_DIM))
                p.setFont(QFont("Segoe UI", 9))
                p.drawText(
                    QRectF(ix, iy + inner * 0.55, inner, inner * 0.3),
                    Qt.AlignmentFlag.AlignCenter,
                    self._center_sub,
                )

        p.end()


class LineChart(QWidget):
    """Линейный график динамики по дням."""

    PAD_LEFT = 90
    PAD_RIGHT = 24
    PAD_TOP = 24
    PAD_BOTTOM = 40
    POINT_R = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points = []              # [(label, value)]
        self.setMinimumHeight(260)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def set_points(self, points):
        self._points = points or []
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._points:
            p.setPen(QColor(TEXT_DIM))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет данных")
            p.end()
            return

        w = self.width()
        h = self.height()
        x0 = self.PAD_LEFT
        x1 = w - self.PAD_RIGHT
        y0 = self.PAD_TOP
        y1 = h - self.PAD_BOTTOM

        values = [v for _, v in self._points]
        vmin = min(values + [0])
        vmax = max(values + [0])
        if vmax == vmin:
            vmax = vmin + 1

        def ypix(v):
            return y1 - (v - vmin) / (vmax - vmin) * (y1 - y0)

        # Сетка + подписи оси Y
        p.setFont(QFont("Segoe UI", 8))
        steps = 4
        for i in range(steps + 1):
            val = vmin + (vmax - vmin) * i / steps
            yy = ypix(val)
            p.setPen(QPen(QColor("#2A2A2A"), 1, Qt.PenStyle.DashLine))
            p.drawLine(int(x0), int(yy), int(x1), int(yy))
            p.setPen(QColor(TEXT_DIM))
            p.drawText(
                QRectF(0, yy - 8, self.PAD_LEFT - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _fmt_int(val),
            )

        # Нулевая линия
        if vmin < 0 < vmax:
            p.setPen(QPen(QColor("#444444"), 1))
            p.drawLine(int(x0), int(ypix(0)), int(x1), int(ypix(0)))

        n = len(self._points)
        if n == 1:
            coords = [QPointF((x0 + x1) / 2, ypix(values[0]))]
        else:
            step = (x1 - x0) / (n - 1)
            coords = [QPointF(x0 + i * step, ypix(v)) for i, v in enumerate(values)]

        # Заливка под линией
        poly = QPolygonF()
        poly.append(QPointF(coords[0].x(), ypix(0)))
        for c in coords:
            poly.append(c)
        poly.append(QPointF(coords[-1].x(), ypix(0)))
        p.setBrush(QBrush(QColor(ACCENT + "33", )))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(poly)

        # Линия
        p.setPen(QPen(QColor(ACCENT), 2))
        for i in range(len(coords) - 1):
            p.drawLine(coords[i], coords[i + 1])

        # Точки + подписи X
        p.setFont(QFont("Segoe UI", 8))
        for i, (label, val) in enumerate(self._points):
            c = coords[i]
            p.setBrush(QBrush(QColor(ACCENT)))
            p.setPen(QPen(QColor(BG), 2))
            p.drawEllipse(c, self.POINT_R, self.POINT_R)
            p.setPen(QColor(TEXT_DIM))
            p.drawText(
                QRectF(c.x() - 40, y1 + 6, 80, 16),
                Qt.AlignmentFlag.AlignCenter,
                str(label),
            )

        p.end()


class HBar(QFrame):
    """Горизонтальный бар: подпись — полоса — значение."""

    LABEL_WIDTH = 250
    VALUE_WIDTH = 170

    def __init__(self, label, value, max_value, color=None,
                 value_text=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.setStyleSheet("QFrame { background: transparent; }")

        if color is None:
            color = ACCENT

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._full_label = str(label)
        self._label = QLabel(self)
        self._label.setFixedWidth(self.LABEL_WIDTH)
        self._label.setStyleSheet(f"color: {TEXT}; background: transparent;")
        self._label.setToolTip(self._full_label)
        lay.addWidget(self._label)

        area = QFrame()
        area.setFixedHeight(12)
        area.setStyleSheet("QFrame { background: transparent; }")
        area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self.bar = QFrame(area)
        self.bar.setStyleSheet(
            f"QFrame {{ background-color: {color}; border-radius: 6px; }}"
        )

        self._area = area
        self._max = max_value
        self._value = value
        lay.addWidget(area, 1)

        txt = value_text if value_text is not None else str(value)
        vlab = QLabel(txt)
        vlab.setFixedWidth(self.VALUE_WIDTH)
        vlab.setStyleSheet(
            f"color: {TEXT}; font-family: Consolas; font-size: 12px; "
            f"background: transparent;"
        )
        vlab.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        lay.addWidget(vlab)

        self._elide()

    def _elide(self):
        try:
            fm = QFontMetrics(self._label.font())
            self._label.setText(fm.elidedText(
                self._full_label, Qt.TextElideMode.ElideRight,
                self.LABEL_WIDTH - 4,
            ))
        except Exception:
            self._label.setText(self._full_label)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update()

    def showEvent(self, e):
        super().showEvent(e)
        self._update()
        self._elide()

    def _update(self):
        try:
            cw = self._area.width()
            ch = self._area.height()
            if self._max > 0:
                w = int(cw * abs(self._value) / self._max)
            else:
                w = 0
            self.bar.setGeometry(0, 0, max(0, w), ch)
        except Exception:
            pass


# =========================================================
# ДАШБОРД
# =========================================================
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
        self._gm_code = self._initial_gm_code

        self._setup_ui()
        self.refresh()

    # ---------------------------------------------------------
    def _setup_ui(self):
        root = QVBoxLayout(self)
        m = 8 if self._is_embedded else 16
        root.setContentsMargins(16, m, 16, m)
        root.setSpacing(12)

        top = QHBoxLayout()
        top.addStretch()

        self.btn_export = SecondaryButton(
            "Сохранить как PNG", on_click=self._export_png, parent=self
        )
        self.btn_export.setMinimumWidth(200)
        self.btn_export.setMinimumHeight(40)
        ic = get_icon_simple("download", color=TEXT, size=16)
        if not ic.isNull():
            self.btn_export.setIcon(ic)
            self.btn_export.setIconSize(QSize(16, 16))
        top.addWidget(self.btn_export)
        root.addLayout(top)

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
        self.main_layout.setSpacing(16)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self.scroll_content = content

    # ---------------------------------------------------------
    def _card(self, min_h: int = 0):
        card = QFrame(self.scroll_content)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 12px;
            }}
        """)
        if min_h:
            card.setMinimumHeight(min_h)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        return card, lay

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 10px; font-weight: bold; "
            f"letter-spacing: 1.2px; background: transparent;"
        )
        return lbl

    def _stat(self, label, value, color=TEXT, sub=""):
        w = QFrame()
        w.setStyleSheet("QFrame { background: transparent; }")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        l = QLabel(label)
        l.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; font-weight: bold; "
            f"letter-spacing: 0.5px; background: transparent;"
        )
        lay.addWidget(l)

        v = QLabel(value)
        v.setStyleSheet(
            f"color: {color}; font-size: 22px; font-weight: bold; "
            f"background: transparent;"
        )
        v.setWordWrap(True)
        lay.addWidget(v)

        if sub:
            s = QLabel(sub)
            s.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
            )
            lay.addWidget(s)

        return w

    def _clear(self):
        while self.main_layout.count():
            it = self.main_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
            ch = it.layout()
            if ch is not None:
                while ch.count():
                    sub = ch.takeAt(0)
                    sw = sub.widget()
                    if sw is not None:
                        sw.deleteLater()

    # ---------------------------------------------------------
    def _refresh_all(self):
        self._clear()

        gm = self._gm_code or self._initial_gm_code
        if not gm:
            hint = QLabel("Выберите инвентаризацию в Архиве")
            hint.setFont(self.FONTS['title'])
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(f"color: {TEXT_DIM}; padding: 60px 20px;")
            self.main_layout.addWidget(hint)
            self.main_layout.addStretch()
            return

        try:
            s = summary(gm)
        except Exception as e:
            log.exception(f"DashboardFrame: {e}")
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

            h = QLabel("Соберите письма: «Забрать информацию» в Архиве.")
            h.setStyleSheet(f"color: {TEXT_DIM};")
            h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.main_layout.addWidget(h)
            self.main_layout.addStretch()
            return

        self._build_header(s)
        self._build_totals(s)
        self._build_zones_pie(s)
        self._build_dynamics(gm)
        self._build_all_zones(gm)
        self._build_time_finance(s, gm)
        self._build_cash_quality(s)

        self.main_layout.addStretch()

    # ---------------------------------------------------------
    def _build_header(self, s):
        card, lay = self._card()

        t = QLabel(f"ГМ {s.get('gm_code', '')} — {s.get('gm_name', '')}")
        t.setStyleSheet(
            f"color: {TEXT}; font-size: 24px; font-weight: bold; "
            f"background: transparent;"
        )
        t.setWordWrap(True)
        lay.addWidget(t)

        fd = s.get("final_details") or {}
        parts = []
        if s.get("start_date") and s.get("end_date"):
            parts.append(f"{s['start_date']} — {s['end_date']}")
        if s.get("duration_text"):
            parts.append(s["duration_text"])
        elif s.get("duration_days"):
            parts.append(f"{s['duration_days']} суток")
        if s.get("variant"):
            parts.append(f"Вариант {s['variant']}")
        if fd.get("gm_format"):
            parts.append(f"Формат: {fd['gm_format']}")
        if fd.get("last_period"):
            parts.append(f"Период: {fd['last_period']}")

        if parts:
            m = QLabel("   ·   ".join(parts))
            m.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 13px; background: transparent;"
            )
            m.setWordWrap(True)
            lay.addWidget(m)

        comm = fd.get("commission") or []
        if comm:
            lay.addSpacing(4)
            lay.addWidget(self._section("СОСТАВ КОМИССИИ"))
            for person in comm:
                name = person.get("name", "")
                role = person.get("role", "")
                txt = name + (f"  —  {role}" if role else "")
                p = QLabel("•  " + txt)
                p.setStyleSheet(
                    f"color: {TEXT}; font-size: 13px; background: transparent;"
                )
                lay.addWidget(p)

        self.main_layout.addWidget(card)

    # ---------------------------------------------------------
    def _build_totals(self, s):
        card, lay = self._card()
        lay.addWidget(self._section("ИТОГИ ПОЛНОЙ ИНВЕНТАРИЗАЦИИ"))

        row = QHBoxLayout()
        row.setSpacing(28)

        ft = s.get("final_totals") or {}
        with_rm = (ft.get("with_rm") or {}).get("amount")
        without_rm = (ft.get("without_rm") or {}).get("amount")
        module = (s.get("final_details") or {}).get("module_deviation") or {}

        row.addWidget(self._stat(
            "С РМ И МЦ", _fmt_money(with_rm),
            _type_color(with_rm), _type_word(with_rm).capitalize(),
        ), 1)

        row.addWidget(self._stat(
            "БЕЗ РМ И МЦ", _fmt_money(without_rm),
            _type_color(without_rm), _type_word(without_rm).capitalize(),
        ), 1)

        if module.get("amount"):
            row.addWidget(self._stat(
                "МОДУЛЬ ОТКЛОНЕНИЙ",
                _fmt_money(module["amount"]),
                ACCENT, "сумма по модулю",
            ), 1)

        lay.addLayout(row)
        self.main_layout.addWidget(card)

    # ---------------------------------------------------------
    def _build_zones_pie(self, s):
        try:
            zones = top_zones(self._gm_code)
        except Exception:
            zones = []

        zones = [z for z in zones if abs(z[1]) > 0]
        if not zones:
            return

        card, lay = self._card()
        lay.addWidget(self._section("ПОТЕРИ ПО АНАЛИТИЧЕСКИМ ЗОНАМ"))

        row = QHBoxLayout()
        row.setSpacing(24)

        # Круговая
        pie_data = [(name, total, get_zone_color(name))
                    for name, total, _d, _s in zones]
        grand = sum(v for _, v, _ in pie_data)

        pie = DonutChart(
            pie_data,
            center_text=_fmt_int(grand),
            center_sub="итого",
        )
        pie.setMinimumSize(380, 380)
        row.addWidget(pie, 1)

        # Легенда
        leg = QFrame()
        leg.setStyleSheet("QFrame { background: transparent; }")
        leg_lay = QVBoxLayout(leg)
        leg_lay.setContentsMargins(0, 0, 0, 0)
        leg_lay.setSpacing(6)
        leg_lay.addStretch()

        for name, total, deficit, surplus in zones:
            entry = QHBoxLayout()
            entry.setSpacing(8)

            dot = QLabel("●")
            dot.setStyleSheet(
                f"color: {get_zone_color(name)}; font-size: 15px; "
                f"background: transparent;"
            )
            entry.addWidget(dot)

            nm = QLabel(name)
            nm.setStyleSheet(
                f"color: {TEXT}; font-size: 12px; background: transparent;"
            )
            entry.addWidget(nm)
            entry.addStretch()

            pct = (abs(total) / grand * 100) if grand else 0
            val = QLabel(
                f"{_fmt_money(total)}  {pct:.0f}%".replace(".0%", "%")
            )
            val.setStyleSheet(
                f"color: {_type_color(total)}; font-size: 11px; "
                f"font-family: Consolas; background: transparent;"
            )
            entry.addWidget(val)

            wrap = QWidget()
            wrap.setStyleSheet("QWidget { background: transparent; }")
            wrap.setLayout(entry)
            leg_lay.addWidget(wrap)

        leg_lay.addStretch()
        row.addWidget(leg, 1)

        push = QWidget()
        push.setStyleSheet("QWidget { background: transparent; }")
        push.setLayout(row)
        lay.addWidget(push)

        self.main_layout.addWidget(card)

    # ---------------------------------------------------------
    def _build_dynamics(self, gm):
        try:
            hist = summary_history(gm)
        except Exception:
            hist = []

        if len(hist) < 2:
            return

        card, lay = self._card()
        lay.addWidget(self._section("ДИНАМИКА ПО ДНЯМ"))

        points = []
        for h in hist:
            d = h.get("date", "")
            short = d[:5] if d else ""
            points.append((short, h.get("grand_total", 0) or 0))

        chart = LineChart()
        chart.set_points(points)
        lay.addWidget(chart)

        self.main_layout.addWidget(card)

    # ---------------------------------------------------------
    def _build_all_zones(self, gm):
        try:
            zones = top_zones(gm)
        except Exception:
            zones = []

        zones = [z for z in zones if abs(z[1]) > 0]
        if not zones:
            return

        card, lay = self._card()
        lay.addWidget(self._section("ВСЕ ЗОНЫ — ОТКЛОНЕНИЯ"))

        max_val = max(abs(z[1]) for z in zones)

        for name, total, deficit, surplus in zones:
            lay.addWidget(HBar(
                name, total, max_val,
                color=get_zone_color(name),
                value_text=f"{_fmt_money(total)}  ({_type_word(total)})",
            ))

        self.main_layout.addWidget(card)

    # ---------------------------------------------------------
    def _build_time_finance(self, s, gm):
        row = QHBoxLayout()
        row.setSpacing(18)

        # --- Часы ревизоров ---
        try:
            hours = time_total(gm)
        except Exception:
            hours = []

        if hours:
            card, lay = self._card()
            lay.addWidget(self._section("ЧАСЫ РЕВИЗОРОВ"))
            max_h = max((h for _, h in hours), default=1)
            for person, h in hours:
                lay.addWidget(HBar(
                    person, h, max_h,
                    color=WARN,
                    value_text=f"{h:.1f} ч".replace(".", ","),
                ))
            row.addWidget(card, 1)

        # --- Финансы ---
        fin = (s.get("final_details") or {}).get("finance") or {}
        if any(fin.get(k) for k in ("sales",)):
            card, lay = self._card()
            lay.addWidget(self._section("ФИНАНСЫ ЗА ПЕРИОД"))

            if fin.get("sales"):
                lay.addWidget(self._stat(
                    "ПРОДАЖИ", _fmt_money(fin["sales"], sign=False), TEXT
                ))

            wo = fin.get("writeoff") or {}
            if wo.get("amount") is not None:
                lay.addWidget(self._stat(
                    "СПИСАНИЯ", _fmt_money(wo["amount"], sign=False),
                    ERROR, _fmt_percent(wo.get("percent")) + " от продаж",
                ))

            inv = fin.get("inventory") or {}
            if inv.get("amount") is not None:
                lay.addWidget(self._stat(
                    "ИНВЕНТАРИЗАЦИИ", _fmt_money(inv["amount"], sign=False),
                    WARN, _fmt_percent(inv.get("percent")) + " от продаж",
                ))

            tot = fin.get("total") or {}
            if tot.get("amount") is not None:
                lay.addWidget(self._stat(
                    "ИТОГО ОТКЛОНЕНИЙ", _fmt_money(tot["amount"], sign=False),
                    ACCENT, _fmt_percent(tot.get("percent")) + " от продаж",
                ))

            row.addWidget(card, 1)

        if row.count():
            wrap = QWidget()
            wrap.setStyleSheet("QWidget { background: transparent; }")
            wrap.setLayout(row)
            self.main_layout.addWidget(wrap)

    # ---------------------------------------------------------
    def _build_cash_quality(self, s):
        fd = s.get("final_details") or {}
        cash = fd.get("cash") or {}
        q = fd.get("quality") or {}

        plan = cash.get("plan")
        fact = cash.get("fact")
        res = cash.get("result") or ""
        qp = q.get("percent")
        ql = q.get("level") or ""

        if plan is None and fact is None and qp is None:
            return

        row = QHBoxLayout()
        row.setSpacing(18)

        if plan is not None or fact is not None:
            card, lay = self._card()
            lay.addWidget(self._section("КАССА ГК"))

            r = QHBoxLayout()
            r.setSpacing(24)
            r.addWidget(self._stat("ПО УЧЁТУ", _fmt_money(plan, False)), 1)
            r.addWidget(self._stat("ПО ФАКТУ", _fmt_money(fact, False)), 1)
            lay.addLayout(r)

            if res:
                ok = "не выявл" in res.lower()
                rl = QLabel(res)
                rl.setStyleSheet(
                    f"color: {SUCCESS if ok else ERROR}; font-size: 13px; "
                    f"background: transparent;"
                )
                lay.addWidget(rl)

            row.addWidget(card, 1)

        if qp is not None:
            card, lay = self._card()
            lay.addWidget(self._section("КАЧЕСТВО ТЕХНОЛОГИЙ"))

            lay.addWidget(self._stat(
                "ТОВАРОДВИЖЕНИЕ ГМ",
                f"{qp:.1f} %".replace(".", ","),
                SUCCESS if qp >= 80 else WARN,
                ql.capitalize() if ql else "",
            ))

            # Прогресс-бар
            bar = QFrame()
            bar.setFixedHeight(10)
            bar.setStyleSheet(
                "QFrame { background-color: #2A2A2A; border-radius: 5px; }"
            )
            fill = QFrame(bar)
            fill.setStyleSheet(
                f"QFrame {{ background-color: "
                f"{SUCCESS if qp >= 80 else WARN}; border-radius: 5px; }}"
            )
            fill.setGeometry(0, 0, int(bar.width() * qp / 100), 10)
            lay.addWidget(bar)

            row.addWidget(card, 1)

        if row.count():
            wrap = QWidget()
            wrap.setStyleSheet("QWidget { background: transparent; }")
            wrap.setLayout(row)
            self.main_layout.addWidget(wrap)

    # ---------------------------------------------------------
    def _export_png(self):
        try:
            from config import FOLDERS
            out_dir = os.path.join(FOLDERS.get("info", ""), "Дашборды")
            os.makedirs(out_dir, exist_ok=True)

            stamp = datetime.now().strftime("%Y%m%d_%H%M")
            gm = self._gm_code or "noGM"
            path = os.path.join(out_dir, f"dashboard_{gm}_{stamp}.png")

            if self.scroll_content is None:
                self.show_error("Ошибка", "Нечего экспортировать.")
                return

            pm = self.scroll_content.grab()
            if not pm.save(path, "PNG"):
                self.show_error("Ошибка", f"Не удалось сохранить PNG:\n{path}")
                return

            self.set_status(f"Сохранено: {path}", SUCCESS)
            self.show_success("Готово", f"Дашборд сохранён:\n{path}")

        except Exception as e:
            log.exception("DashboardFrame: ошибка экспорта PNG")
            self.show_error("Ошибка", f"Не удалось сохранить PNG:\n{e}")

    # ---------------------------------------------------------
    def refresh(self):
        self._refresh_all()

    def on_hide(self):
        pass

    def on_close(self):
        pass
