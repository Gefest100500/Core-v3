# ui/components/weather_widget.py
"""
Виджет погоды для главной страницы.

Механизм: один долгоживущий WebView2 (pywv2) на всё приложение.
pywv2 не позволяет создать WebView второй раз в том же процессе —
второй start() падает с "invalid external parent window". Поэтому
WebView создаётся ОДИН раз при первом запросе, а каждое обновление
(раз в 10 минут) выполняется через eval(js) в том же экземпляре.

Источник данных: wttr.in (бесплатно, без ключа, JSON в формате j1).
Запрос идёт из Chromium, поэтому работает и через корпоративный прокси,
где обычный httpx наружу не пробивается.
"""
import json
import os
import threading
import time
import ctypes

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QThread, QTimer, QObject
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel

from ui.components.widgets import create_card
from ui.icons import get_icon_simple
from core.geo_helper import (
    get_local_ip, find_gm_by_ip, get_city_by_gm_code, get_coords_by_city,
)
from utils.file_utils import get_data_dir
from utils.logger import log

try:
    import pywv2
    WEBVIEW_AVAILABLE = True
except ImportError:
    WEBVIEW_AVAILABLE = False
    log.warning("pywv2 не установлен — виджет погоды будет показывать заглушку")


# --- WinAPI для невидимого родительского окна ---
user32 = ctypes.windll.user32
WS_POPUP = 0x80000000
WS_EX_TOOLWINDOW = 0x00000080
SW_HIDE = 0

PROFILE_DIR = os.path.join(get_data_dir(), "weather_profile")

#: Сколько ждать загрузки страницы перед первым запросом.
STARTUP_WAIT_SEC = 2

#: Таймаут одного запроса погоды (секунды).
FETCH_TIMEOUT_SEC = 45

#: Интервал автообновления.
REFRESH_INTERVAL_MS = 10 * 60 * 1000


def create_hidden_window() -> int:
    """Создаёт невидимое родительское окно и возвращает его HWND."""
    hwnd = user32.CreateWindowExW(
        WS_EX_TOOLWINDOW,
        "STATIC",
        "WeatherProxy",
        WS_POPUP,
        0, 0, 0, 0,
        0, 0, 0, 0,
    )
    if hwnd:
        user32.ShowWindow(hwnd, SW_HIDE)
    return hwnd


# Погодные коды Open-Meteo (WMO)
WEATHER_CODES = {
    0: ("Ясно", "sun"),
    1: ("Преим. ясно", "cloud-sun"),
    2: ("Переменная облачность", "cloud-sun"),
    3: ("Пасмурно", "cloud"),
    45: ("Туман", "cloud"),
    48: ("Туман", "cloud"),
    51: ("Морось", "rain"),
    53: ("Морось", "rain"),
    55: ("Морось", "rain"),
    61: ("Дождь", "rain"),
    63: ("Дождь", "rain"),
    65: ("Сильный дождь", "rain"),
    71: ("Снег", "snow"),
    73: ("Снег", "snow"),
    75: ("Сильный снег", "snow"),
    77: ("Снежная крупа", "snow"),
    80: ("Ливень", "rain"),
    81: ("Ливень", "rain"),
    82: ("Сильный ливень", "rain"),
    85: ("Снегопад", "snow"),
    86: ("Снегопад", "snow"),
    95: ("Гроза", "rain"),
    96: ("Гроза", "rain"),
    99: ("Гроза", "rain"),
}


def _wwo_to_wmo(wwo_code) -> int:
    """Переводит код wttr.in (WWO) в код WMO."""
    code = str(wwo_code)
    if code == "113":
        return 0
    if code in ("116", "119", "122"):
        return 3
    if code in ("176", "293", "296", "299", "302", "305", "308"):
        return 61
    if code in ("179", "323", "326", "329", "332", "335", "338"):
        return 71
    if code in ("200", "386", "389", "392", "395"):
        return 95
    return 3


class WeatherWebView:
    """Один долгоживущий WebView для запросов погоды.

    Создаётся лениво при первом обращении и живёт до выхода из приложения.
    Все запросы идут через один и тот же экземпляр.
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._view = None
        self._parent_hwnd = 0
        self._ready = False
        self._fetch_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "WeatherWebView":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # ЖИЗНЕННЫЙ ЦИКЛ
    # ------------------------------------------------------------------
    def _ensure_started(self) -> bool:
        """Создаёт WebView при первом вызове. Повторно не создаёт."""
        if self._view is not None:
            return True

        self._parent_hwnd = create_hidden_window()
        if not self._parent_hwnd:
            log.warning("WeatherWidget: не удалось создать скрытое окно")
            return False

        try:
            self._view = pywv2.WebView(
                title="Weather",
                size=(100, 100),
                user_data_dir=PROFILE_DIR,
                parent_hwnd=self._parent_hwnd,
                auto_pump=True,
                context_menu=False,
            )
            self._view.start()

            try:
                hwnd = self._view.hwnd
                if hwnd:
                    user32.ShowWindow(hwnd, SW_HIDE)
            except Exception:
                pass

            self._view.load_html("<html><body>weather</body></html>")
            time.sleep(STARTUP_WAIT_SEC)
            self._ready = True
            log.info("WeatherWidget: WebView создан (долгоживущий)")
            return True

        except Exception as e:
            log.warning(f"WeatherWidget: не удалось создать WebView: {e}")
            self._shutdown()
            return False

    def _shutdown(self):
        if self._view is not None:
            try:
                self._view.close()
            except Exception:
                pass
            self._view = None
        if self._parent_hwnd:
            try:
                user32.DestroyWindow(self._parent_hwnd)
            except Exception:
                pass
            self._parent_hwnd = 0
        self._ready = False

    def shutdown(self):
        """Вызывается при выходе из приложения."""
        self._shutdown()

    # ------------------------------------------------------------------
    # ЗАПРОС
    # ------------------------------------------------------------------
    def fetch(self, url: str) -> str:
        """Синхронный запрос через уже существующий WebView.

        Возвращает текст ответа. Бросает исключение при ошибке.
        """
        with self._fetch_lock:
            if not self._ensure_started():
                raise RuntimeError("WebView недоступен")

            # load_html создаёт одноразовый документ: в нём XHR может не
            # отработать (origin "null" и политика безопасности WebView2).
            # Поэтому каждый запрос сначала переходим на реальный домен,
            # из контекста которого XHR уже разрешён.
            js = (
                "(function(){"
                "var x=new XMLHttpRequest();"
                f"x.open('GET','{url}',false);"
                "x.send();"
                "return x.responseText;"
                "})()"
            )

            last_error = None
            for attempt in (1, 2):
                try:
                    text = self._view.eval(js)
                except Exception as e:
                    last_error = e
                    text = ""

                if text:
                    return text

                if attempt == 1:
                    log.info("WeatherWidget: пустой ответ, перезагружаем страницу")
                    try:
                        self._view.navigate("https://wttr.in/")
                        time.sleep(STARTUP_WAIT_SEC)
                    except Exception as e:
                        log.warning(f"WeatherWidget: navigate не удался: {e}")

            if last_error is not None:
                raise RuntimeError(f"Запрос не выполнен: {last_error}")

            raise RuntimeError("Пустой ответ от API")


class _FetchResult:
    """Простой контейнер для результата, полученного из главного потока."""

    def __init__(self):
        self.text = ""
        self.error = None


def _run_on_main(fn, timeout_ms: int = FETCH_TIMEOUT_SEC * 1000) -> bool:
    """Выполняет fn в главном потоке и ждёт завершения.

    Если мы уже в главном потоке — просто вызываем. Иначе используем
    QMetaObject.invokeMethod с BlockingQueuedConnection через QTimer.
    """
    app = QApplication.instance()
    if app is None:
        fn()
        return True

    if QThread.currentThread() is app.thread():
        fn()
        return True

    from PyQt6.QtCore import QMetaObject, Qt as QtCore, Q_ARG, QTimer

    done = threading.Event()
    holder = {"done": False}

    class _Bridge(QObject):
        @pyqtSlot()
        def call(self):
            try:
                fn()
            finally:
                holder["done"] = True
                done.set()

    bridge = _Bridge()
    bridge.moveToThread(app.thread())

    QMetaObject.invokeMethod(
        bridge, "call", QtCore.ConnectionType.QueuedConnection
    )

    return done.wait(timeout_ms / 1000.0)


class _WeatherFetchThread(QThread):
    """Один цикл: определить локацию → запросить → вернуть результат.

    ВАЖНО: запрос к WebView выполняется в ГЛАВНОМ потоке через run()
    вызываемого объекта, а не здесь. pywv2 не терпит eval() из чужого
    потока при auto_pump=True — со второго раза приходит пустой ответ.
    Здесь только определение локации, оно безопасно в фоне.
    """

    finished = pyqtSignal(dict)

    def run(self):
        result = {"success": False, "city": ""}
        city = ""

        try:
            ip = get_local_ip()
            code = find_gm_by_ip(ip) if ip else ""
            city = get_city_by_gm_code(code) if code else ""
            coords = get_coords_by_city(city) if city else None

            if not coords:
                raise ValueError("Локация не определена")

            lat, lon = coords
            city = city.capitalize()

            if not WEBVIEW_AVAILABLE:
                raise ValueError("WebView2 недоступен")

            url = f"https://wttr.in/{lat},{lon}?format=j1"

            # PyQt6: вызывать WebView можно только из главного потока.
            # provisionallyCreating здесь неуместен — используем invokeMethod
            # через сигнал, который передаёт QVariant.
            from PyQt6.QtCore import QMetaObject, Qt as QtCore, Q_ARG

            holder = _FetchResult()

            def _do():
                try:
                    holder.text = WeatherWebView.instance().fetch(url)
                except Exception as exc:
                    holder.error = exc

            _run_on_main(_do)

            if holder.error is not None:
                raise holder.error
            text = holder.text

            log.info(f"WeatherWidget: ответ получен, длина {len(text) if text else 0}")

            data = json.loads(text)
            current = data.get("current_condition", [{}])[0]
            temp = float(current.get("temp_C", 0))
            wmo = _wwo_to_wmo(current.get("weatherCode", "113"))

            result = {
                "success": True,
                "city": city,
                "temp": temp,
                "code": wmo,
            }

        except Exception as e:
            log.warning(f"WeatherWidget: ошибка загрузки: {e}")
            result = {"success": False, "error": str(e), "city": city}

        self.finished.emit(result)


class WeatherWidget:
    @staticmethod
    def create(parent, colors, fonts):
        card = create_card(parent)
        card.setFixedWidth(340)
        card.setMinimumHeight(140)

        layout = card.layout()

        top_row = QHBoxLayout()
        top_row.setSpacing(15)
        top_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        icon_label = QLabel(card)
        icon_label.setFixedSize(48, 48)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(icon_label)

        temp_col = QVBoxLayout()
        temp_col.setSpacing(2)

        temp_label = QLabel("—", card)
        font_temp = QFont("Segoe UI", 28)
        font_temp.setBold(True)
        temp_label.setFont(font_temp)
        temp_label.setStyleSheet(f"color: {colors.get('text', '#E0E0E0')};")
        temp_col.addWidget(temp_label)

        desc_label = QLabel("Загрузка...", card)
        desc_label.setFont(fonts['small'])
        desc_label.setStyleSheet(f"color: {colors.get('text_dim', '#A0A0A0')};")
        temp_col.addWidget(desc_label)

        top_row.addLayout(temp_col)
        top_row.addStretch()
        layout.addLayout(top_row)

        city_label = QLabel("Определение локации...", card)
        city_label.setFont(fonts['small'])
        city_label.setStyleSheet(f"color: {colors.get('text_dim', '#A0A0A0')};")
        layout.addWidget(city_label)

        def _update_ui(data):
            city = data.get("city", "")
            if not data.get("success"):
                if city:
                    temp_label.setText("—")
                    desc_label.setText("Погода недоступна")
                    city_label.setText(city)
                    icon = get_icon_simple(
                        "cloud", color=colors.get('text_dim', '#A0A0A0'), size=48
                    )
                    if not icon.isNull():
                        icon_label.setPixmap(icon.pixmap(48, 48))
                else:
                    desc_label.setText("Нет данных")
                    city_label.setText("Локация не определена")
                return

            temp = data.get("temp")
            code = data.get("code")
            if temp is not None:
                temp_label.setText(f"{round(temp)}°C")
            else:
                temp_label.setText("—")

            desc, icon_name = WEATHER_CODES.get(code, ("Неизвестно", "cloud"))
            desc_label.setText(desc)
            city_label.setText(city)

            icon = get_icon_simple(
                icon_name, color=colors.get('text_dim', '#A0A0A0'), size=48
            )
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(48, 48))

        def _fetch():
            thread = _WeatherFetchThread(card)
            thread.finished.connect(_update_ui)
            card._weather_thread = thread
            thread.start()

        _fetch()

        refresh_timer = QTimer(card)
        refresh_timer.timeout.connect(_fetch)
        refresh_timer.start(REFRESH_INTERVAL_MS)

        card._weather_timer = refresh_timer

        return card
