"""Tests for backend.config path handling (bug: lstrip("./") ate leading dots)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import _get_db_path


class TestGetDbPath:
    def test_default_relative_path(self, monkeypatch):
        monkeypatch.delenv("DATABASE_PATH", raising=False)
        path = _get_db_path()
        assert path.endswith(os.path.join("database", "myexa.db"))
        # Must resolve inside the project root, not the CWD
        assert os.path.isabs(path)

    def test_dot_slash_prefix_is_stripped(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATABASE_PATH", "./data/test.db")
        path = _get_db_path()
        assert path.endswith(os.path.join("data", "test.db"))

    def test_hidden_dir_name_is_preserved(self, tmp_path, monkeypatch):
        """A leading ".hidden" directory must NOT lose its dot.

        Regression: the old ``path.lstrip("./")`` stripped any leading '.'
        characters, silently turning ".hidden/db.sqlite" into "hidden/db.sqlite".
        """
        monkeypatch.setenv("DATABASE_PATH", "./.hidden/db.sqlite")
        path = _get_db_path()
        assert path.endswith(os.path.join(".hidden", "db.sqlite"))

    def test_absolute_path_passthrough(self, tmp_path, monkeypatch):
        abs_path = str(tmp_path / "direct.db")
        monkeypatch.setenv("DATABASE_PATH", abs_path)
        assert os.path.normpath(_get_db_path()) == os.path.normpath(abs_path)

    def test_backslash_prefix_also_handled(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATABASE_PATH", ".\\data\\win.db")
        path = _get_db_path()
        assert path.endswith(os.path.join("data", "win.db"))
