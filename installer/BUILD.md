# Сборка Core V3.1

Полная инструкция по созданию установщика.

## Что нужно установить один раз

| Что | Зачем | Ссылка |
|---|---|---|
| Python 3.13 | запуск и сборка | python.org |
| PyInstaller | сборка .exe | `py -3.13 -m pip install pyinstaller` |
| Inno Setup 6 | создание установщика | jrsoftware.org/isdl.php |

Зависимости проекта (все уже в `pyproject.toml`):

```powershell
py -3.13 -m pip install -e ".[win]"
```

`[win]` добавляет `pywin32` и `xlrd` — без них не работают принтеры и чтение `.xls`.

---

## Сборка в один клик

```powershell
.\build.bat
```

Скрипт сделает три шага подряд:

1. **`prepare_build.py`** — удалит личные данные из `data/`
2. **PyInstaller** — соберёт папку `dist\CoreV3\` с `CoreV3.exe`
3. **Inno Setup** — создаст `installer\Output\CoreV3_Setup_3.1.exe`

Если Inno Setup не установлен — скрипт остановится на шаге 3 и скажет об этом.

---

## Сборка по шагам (вручную)

### 1. Очистка личных данных

```powershell
py -3.13 prepare_build.py
```

Удаляет из `data/`:

```
actions_history.json     история действий
active_inventory.json    текущая инвентаризация
inventory_archive.json   архив инвентаризаций
emails.json              письма
gm_notes.json            заметки по ГМ
ml/                      база Shadow Engine
webengine/               кэш браузера (старое)
emails/                  папка писем
notes/                   заметки блокнота
```

**Проверьте результат перед сборкой:** в `data/` должны остаться только
справочники (`gm_data.json`, `gm_ip.json`, `guide.json` и т.д.).

### 2. PyInstaller

```powershell
py -3.13 -m PyInstaller CoreV3.spec --noconfirm
```

Результат: `dist\CoreV3\CoreV3.exe` + библиотеки рядом.

Spec собирает **onedir**, а не onefile. Причина: с PyQt6 и WebView2
onefile распаковывается в `%TEMP%` при каждом запуске и стартует
10–20 секунд вместо 2.

### 3. Inno Setup

Открыть `installer\CoreV3.iss` в Inno Setup Compiler → **Compile**,
или из командной строки:

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\CoreV3.iss
```

Результат: `installer\Output\CoreV3_Setup_3.1.exe`

---

## Что делает установщик

- **Ставит в папку пользователя:** `%LOCALAPPDATA%\Programs\CoreV3\`
- **Права администратора не нужны** (`PrivilegesRequired=lowest`)
- **Проверяет WebView2 Runtime** при старте и предлагает скачать, если нет
- **Создаёт ярлыки:** в меню «Пуск», опционально на рабочем столе и в панели задач
- **При удалении** сносит `Logs\`, `temp\`, `__pycache__`, но **не трогает `data\`** — данные пользователя остаются

---

## Поменять версию

Версия задаётся в трёх местах — их надо менять согласованно:

| Файл | Что |
|---|---|
| `installer\CoreV3.iss` | `#define AppVersion "3.1"` |
| `build.bat` | `set VERSION=3.1` |
| `pyproject.toml` | `version = "3.1.0"` |

Из `AppVersion` в `.iss` автоматически собирается имя файла:
`CoreV3_Setup_3.1.exe`.

---

## Проверка собранного установщика

1. Запустить `CoreV3_Setup_3.1.exe`
2. Пройти мастер установки
3. Запустить Core V3 из меню «Пуск»
4. Убедиться, что:
   - программа открывается без ошибок
   - вкладки переключаются (10 штук)
   - в `%LOCALAPPDATA%\Programs\CoreV3\data\` нет личных данных
   - мастер первого запуска появляется при первом старте
5. Удалить через «Установка и удаление программ» — `data\` должна остаться

---

## Типичные проблемы

### PyInstaller не находит модуль

Добавьте его в `hiddenimports` в `CoreV3.spec` и пересоберите.

### Программа падает при запуске, а из исходников работает

Запустите собранный `.exe` из консоли, чтобы увидеть ошибку:

```powershell
cd dist\CoreV3
.\CoreV3.exe
```

Если окна нет, а ошибка есть — смените в `CoreV3.spec` `console=False` на `console=True`,
пересоберите и посмотрите вывод.

### Антивирус ругается на установщик

Обычная реакция на неподписанный PyInstaller-бинарник. Лечится подписью кода
(сертификат) или добавлением в исключения у пользователей.

### Размер установщика большой

Ожидаемо: PyQt6 + Qt — около 150 МБ в сжатом виде. Уменьшить можно,
исключив неиспользуемые модули Qt в `CoreV3.spec` (`excludes`), но осторожно:
легко отрезать нужное.
