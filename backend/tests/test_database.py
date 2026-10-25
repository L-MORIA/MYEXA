"""Tests for backend.api.database.Database."""

from api.database import Database


class TestDatabaseInit:
    def test_creates_tables(self, tmp_db_path, monkeypatch):
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        db = Database()
        # If no exception, tables were created successfully
        import sqlite3
        conn = sqlite3.connect(tmp_db_path)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "search_results" in tables
        assert "custom_sites" in tables
        assert "search_history" in tables


class TestCustomSites:
    def test_add_and_get(self, tmp_db_path, monkeypatch):
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        db = Database()

        db.add_custom_site("https://example.com", "Example", "test", "tag1")
        sites = db.get_custom_sites()
        assert len(sites) >= 1
        row = sites[0]
        assert row["url"] == "https://example.com"
        assert row["title"] == "Example"

    def test_add_duplicate_ignored(self, tmp_db_path, monkeypatch):
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        db = Database()

        db.add_custom_site("https://dup.com", "Dup")
        db.add_custom_site("https://dup.com", "Dup2")
        sites = db.get_custom_sites()
        assert len(sites) == 1

    def test_delete_by_id(self, tmp_db_path, monkeypatch):
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        db = Database()

        db.add_custom_site("https://del.com", "Delete Me")
        sites = db.get_custom_sites()
        site_id = sites[0]["id"]

        success = db.delete_custom_site(site_id)
        assert success is True

        sites_after = db.get_custom_sites()
        assert len(sites_after) == 0

    def test_delete_nonexistent_returns_false(self, tmp_db_path, monkeypatch):
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        db = Database()
        assert db.delete_custom_site(99999) is False

    def test_row_factory_is_row(self, tmp_db_path, monkeypatch):
        """get_custom_sites should return sqlite3.Row objects (dict-like)."""
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        db = Database()

        db.add_custom_site("https://x.com", "X")
        sites = db.get_custom_sites()
        row = sites[0]
        # Row supports both index and key access
        assert row["title"] == "X"
        assert row[1] == "https://x.com"


class TestSaveResult:
    def test_save_and_get(self, tmp_db_path, monkeypatch):
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        db = Database()

        db.save_result("test query", "https://r.com", "Result", "content", 0.85, "en", "exa")
        results = db.get_results("test query")
        assert len(results) >= 1
        assert results[0]["url"] == "https://r.com"

    def test_duplicate_url_ignored(self, tmp_db_path, monkeypatch):
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        db = Database()

        db.save_result("q", "https://u.com", "T", "c", 0.9, "en", "exa")
        db.save_result("q", "https://u.com", "T2", "c2", 0.8, "en", "exa")
        results = db.get_results("q")
        assert len(results) == 1


class TestSearchHistory:
    def test_save_history(self, tmp_db_path, monkeypatch):
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        db = Database()
        db.save_search_history("hello", "ru,en", 15)
        # No exception = success (we don't have a getter for history)


class TestDatabaseDirectoryCreation:
    """Regression: a fresh clone crashed because the database directory
    was never created (README promises it is auto-created)."""

    def test_creates_missing_nested_directory(self, tmp_path, monkeypatch):
        import os
        from config import Config
        nested = str(tmp_path / "deeply" / "nested" / "dir" / "test.db")
        monkeypatch.setattr(Config, "DATABASE_PATH", nested)
        Database()  # must not raise
        assert os.path.isdir(str(tmp_path / "deeply" / "nested" / "dir"))

    def test_works_when_dir_already_exists(self, tmp_db_path, monkeypatch):
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        Database()
        Database()  # second init must also succeed

    def test_query_index_created(self, tmp_db_path, monkeypatch):
        import sqlite3
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        Database()
        conn = sqlite3.connect(tmp_db_path)
        indexes = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        conn.close()
        assert "idx_search_results_query" in indexes
