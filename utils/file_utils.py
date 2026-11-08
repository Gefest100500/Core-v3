# utils/file_utils.py
"""Утилиты для работы с файлами и папками."""
import sys
import os
import shutil
from pathlib import Path
from utils.logger import log


def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve().parent)
    else:
        return str(Path(__file__).resolve().parent.parent)


def get_bundled_data_dir() -> str:
    """Папка со встроенными дефолтными JSON (только чтение)."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", get_base_dir())
        return os.path.join(base, "data")
    else:
        return os.path.join(get_base_dir(), "data")


def get_app_data_root() -> str:
    try:
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata and os.path.isdir(local_appdata):
            return os.path.join(local_appdata, "Core_V3_0")
    except (OSError, PermissionError):
        pass
    return get_base_dir()


def get_user_data_dir() -> str:
    path = os.path.join(get_base_dir(), "data")
    os.makedirs(path, exist_ok=True)
    return path


def get_data_dir() -> str:
    """Единая папка данных: data/ рядом с .exe (или с проектом при разработке)."""
    return get_user_data_dir()


def get_logs_dir() -> str:
    path = os.path.join(get_base_dir(), "Logs")
    os.makedirs(path, exist_ok=True)
    return path


def get_input_dir() -> str:
    path = os.path.join(get_base_dir(), "Файлы")
    os.makedirs(path, exist_ok=True)
    return path


def get_generated_dir() -> str:
    path = os.path.join(get_base_dir(), "Готовые")
    os.makedirs(path, exist_ok=True)
    return path


def get_output_dir() -> str:
    return get_generated_dir()


def get_temp_dir() -> str:
    path = os.path.join(get_base_dir(), "temp")
    os.makedirs(path, exist_ok=True)
    return path


def clear_folder(folder_path):
    if not os.path.isdir(folder_path):
        log.debug(f"clear_folder: папки нет — {folder_path}")
        return (0, 0)
    removed = 0
    failed = 0
    try:
        entries = os.listdir(folder_path)
    except (OSError, PermissionError) as e:
        log.warning(f"clear_folder: не удалось прочитать {folder_path}: {e}")
        return (0, 0)
    for entry in entries:
        full_path = os.path.join(folder_path, entry)
        try:
            if os.path.isfile(full_path) or os.path.islink(full_path):
                os.remove(full_path)
                removed += 1
            elif os.path.isdir(full_path):
                shutil.rmtree(full_path)
                removed += 1
        except (OSError, PermissionError) as e:
            failed += 1
            log.debug(f"clear_folder: не удалось удалить {full_path}: {e}")
    if failed:
        log.warning(f"clear_folder: {folder_path} — удалено {removed}, не удалось {failed}")
    else:
        log.debug(f"clear_folder: {folder_path} — удалено {removed}")
    return (removed, failed)


def style_excel(file_path, header_row=1, start_col=1, end_col=None):
    from openpyxl import load_workbook
    if isinstance(file_path, str):
        if not os.path.exists(file_path):
            return
        wb = load_workbook(file_path)
        for sheet_name in wb.sheetnames:
            _style_worksheet(wb[sheet_name], header_row, start_col, end_col)
        wb.save(file_path)
    else:
        _style_worksheet(file_path, header_row, start_col, end_col)


def _style_worksheet(worksheet, header_row=1, start_col=1, end_col=None):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    if end_col is None:
        end_col = worksheet.max_column
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="D42626", end_color="D42626", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(style="thin", color="FFFFFF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col in range(start_col, end_col + 1):
        cell = worksheet.cell(row=header_row, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = border
    for col in range(start_col, end_col + 1):
        column_letter = get_column_letter(col)
        max_length = 10
        for row in range(1, worksheet.max_row + 1):
            cell_value = worksheet.cell(row=row, column=col).value
            if cell_value:
                max_length = max(max_length, len(str(cell_value)))
        worksheet.column_dimensions[column_letter].width = min(max_length + 2, 60)
    worksheet.freeze_panes = worksheet.cell(row=header_row + 1, column=1)