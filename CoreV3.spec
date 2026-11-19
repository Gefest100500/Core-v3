# CoreV3.spec
# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec для Core V3.1.

Собирает папку (onedir), а не один .exe: с PyQt6 и WebView2 onefile
распаковывается при каждом запуске и стартует 10-20 секунд.

Сборка:
    py -3.13 -m PyInstaller CoreV3.spec --noconfirm

Результат:
    dist/CoreV3/CoreV3.exe
"""
import os

from PyInstaller.utils.hooks import collect_submodules

BASE_DIR = os.path.abspath(os.getcwd())

# ---- Данные приложения -------------------------------------------------
datas = []

# Иконки UI (SVG)
datas.append((os.path.join(BASE_DIR, "ui", "icons"), os.path.join("ui", "icons")))

# Справочники — в data/ рядом с .exe. Личные данные отсекаются
# скриптом prepare_build.py до сборки.
SPRAVOCHNIKI = [
    "gm_data.json",
    "gm_ip.json",
    "standard_comments.json",
    "inventory_plans.json",
    "kv_rules.json",
    "kv_reason_schema.json",
    "unwanted.json",
    "timesheet.json",
    "gm_cities_cache.json",
    "guide.json",
    "checklists.json",
    "steal_codes.json",
    "distance_history.json",
    "user_settings.json",
]

for name in SPRAVOCHNIKI:
    path = os.path.join(BASE_DIR, "data", name)
    if os.path.isfile(path):
        datas.append((path, "data"))

# ---- Скрытые импорты ---------------------------------------------------
hiddenimports = [
    "PyQt6.QtPrintSupport",
    "PyQt6.QtSvg",
    "PyQt6.QtNetwork",
    "win32print",
    "win32com",
    "win32com.client",
    "pythoncom",
    "pywintypes",
]

# Подмодули проекта, которые PyInstaller может не увидеть
for package in ("core", "ui", "utils", "ml"):
    hiddenimports += collect_submodules(package)

# ---- Исключения --------------------------------------------------------
excludes = [
    "tkinter",
    "matplotlib",
    "scipy",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
]


a = Analysis(
    [os.path.join(BASE_DIR, "main.py")],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CoreV3",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(BASE_DIR, "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CoreV3",
)
