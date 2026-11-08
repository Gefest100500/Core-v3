# tests/test_data_dir.py
"""
Тесты для get_data_dir().

Новая логика: данные всегда лежат в data/ рядом с .exe
(или с корнем проекта при разработке). %LOCALAPPDATA% больше
не используется для data.
"""
import os

from utils import file_utils


def test_get_data_dir_uses_base_dir(monkeypatch, tmp_path):
    """get_data_dir() идёт в get_base_dir()/data, а не в LOCALAPPDATA."""
    fake_base = tmp_path / "Base"
    fake_base.mkdir()
    monkeypatch.setattr(
        "utils.file_utils.get_base_dir",
        lambda: str(fake_base),
    )

    # Даже если LOCALAPPDATA выставлена — она игнорируется
    fake_local = tmp_path / "LocalAppData"
    fake_local.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))

    path = file_utils.get_data_dir()

    assert path == os.path.join(str(fake_base), "data")
    assert os.path.isdir(path)


def test_get_data_dir_fallback_without_local_appdata(monkeypatch, tmp_path):
    """Без LOCALAPPDATA — всё равно get_base_dir()/data."""
    fake_base = tmp_path / "Base"
    fake_base.mkdir()
    monkeypatch.setattr(
        "utils.file_utils.get_base_dir",
        lambda: str(fake_base),
    )
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    path = file_utils.get_data_dir()

    assert path == os.path.join(str(fake_base), "data")
    assert os.path.isdir(path)


def test_get_data_dir_creates_folder(monkeypatch, tmp_path):
    """Папка data создаётся при первом вызове рядом с base."""
    fake_base = tmp_path / "Base"
    fake_base.mkdir()
    monkeypatch.setattr(
        "utils.file_utils.get_base_dir",
        lambda: str(fake_base),
    )

    expected = os.path.join(str(fake_base), "data")
    assert not os.path.isdir(expected)

    file_utils.get_data_dir()

    assert os.path.isdir(expected)