@echo off
REM ============================================================
REM  build.bat — сборка Core V3.1 (PyInstaller + Inno Setup)
REM
REM  Запуск из папки проекта:
REM      build.bat
REM
REM  Шаги:
REM   1. очистка личных данных (prepare_build.py)
REM   2. PyInstaller -> dist\CoreV3\
REM   3. Inno Setup -> installer\Output\CoreV3_Setup_3.1.exe
REM ============================================================

setlocal enabledelayedexpansion

set VERSION=3.1
set PYTHON=py -3.13

echo.
echo ============================================================
echo   Сборка Core V3.%VERSION%
echo ============================================================
echo.

REM ---------- 1. Очистка личных данных ----------
echo [1/3] Очистка личных данных...
%PYTHON% prepare_build.py
if errorlevel 1 (
    echo.
    echo ОШИБКА: prepare_build.py завершился с ошибкой.
    goto :error
)
echo.

REM ---------- 2. PyInstaller ----------
echo [2/3] Сборка через PyInstaller...

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

%PYTHON% -m PyInstaller CoreV3.spec --noconfirm
if errorlevel 1 (
    echo.
    echo ОШИБКА: PyInstaller завершился с ошибкой.
    goto :error
)

if not exist "dist\CoreV3\CoreV3.exe" (
    echo.
    echo ОШИБКА: dist\CoreV3\CoreV3.exe не создан.
    goto :error
)
echo   Готово: dist\CoreV3\CoreV3.exe
echo.

REM ---------- 3. Inno Setup ----------
echo [3/3] Сборка установщика...

set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe

if "!ISCC!"=="" (
    echo.
    echo   ВНИМАНИЕ: Inno Setup 6 не найден.
    echo   Установите его с https://jrsoftware.org/isdl.php
    echo   или соберите установщик вручную: installer\CoreV3.iss
    echo.
    echo   Программа собрана: dist\CoreV3\CoreV3.exe
    goto :done
)

"!ISCC!" installer\CoreV3.iss
if errorlevel 1 (
    echo.
    echo ОШИБКА: Inno Setup завершился с ошибкой.
    goto :error
)

echo.
echo   Готово: installer\Output\CoreV3_Setup_%VERSION%.exe

:done
echo.
echo ============================================================
echo   СБОРКА ЗАВЕРШЕНА
echo ============================================================
echo.
echo   Программа:  dist\CoreV3\CoreV3.exe
echo   Установщик: installer\Output\CoreV3_Setup_%VERSION%.exe
echo.
goto :eof

:error
echo.
echo ============================================================
echo   СБОРКА ПРЕРВАНА
echo ============================================================
exit /b 1
