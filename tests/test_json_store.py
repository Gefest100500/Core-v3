# tests/test_json_store.py
"""
Тесты безопасного чтения JSON: битые файлы не должны ломать приложение.
"""
import json
import os

from utils.json_store import load_json


class TestLoadJson:
    def test_reads_valid_file(self, tmp_path):
        path = tmp_path / "data.json"
        path.write_text('{"a": 1}', encoding="utf-8")
        assert load_json(str(path), default={}) == {"a": 1}

    def test_missing_file_returns_default(self, tmp_path):
        path = tmp_path / "nope.json"
        assert load_json(str(path), default={"x": 2}) == {"x": 2}

    def test_broken_file_returns_default_and_backup(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text('{"a": 1', encoding="utf-8")

        result = load_json(str(path), default={})

        assert result == {}
        backups = [p for p in os.listdir(tmp_path) if ".broken-" in p]
        assert len(backups) == 1
        # Копия должна содержать исходный битый текст — чтобы можно было разобрать
        with open(tmp_path / backups[0], encoding="utf-8") as f:
            assert f.read() == '{"a": 1'

    def test_backup_can_be_disabled(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("не json", encoding="utf-8")

        assert load_json(str(path), default=[], backup_broken=False) == []
        assert not [p for p in os.listdir(tmp_path) if ".broken-" in p]

    def test_bom_file_is_read(self, tmp_path):
        path = tmp_path / "bom.json"
        path.write_text('\ufeff{"b": 3}', encoding="utf-8")

        assert load_json(str(path), default={}) == {"b": 3}

    def test_list_default(self, tmp_path):
        path = tmp_path / "list.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        assert load_json(str(path), default=[]) == [1, 2, 3]

    def test_original_file_not_deleted(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{oops", encoding="utf-8")

        load_json(str(path), default={})

        assert path.exists()
        assert path.read_text(encoding="utf-8") == "{oops"
