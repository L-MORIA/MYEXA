"""Tests for backend.api.database.Database."""

from api.database import Database


class TestDatabaseInit:
    def test_creates_tables(self, tmp_db_path, monkeypatch):
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        Database()
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

    def test_same_url_saved_for_two_queries(self, tmp_db_path, monkeypatch):
        """A page found for two different queries must be kept for both.

        With the old global UNIQUE(url) the second insert was swallowed, so the
        history of the second query lost the hit entirely.
        """
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        db = Database()

        db.save_result("first query", "https://u.com", "T", "c", 0.9, "en", "exa")
        db.save_result("second query", "https://u.com", "T", "c", 0.8, "ru", "exa")

        assert len(db.get_results("first query")) == 1
        assert len(db.get_results("second query")) == 1

    def test_duplicate_url_updates_existing_row(self, tmp_db_path, monkeypatch):
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        db = Database()

        db.save_result("q", "https://u.com", "Old", "c", 0.1, "en", "exa")
        db.save_result("q", "https://u.com", "New", "c2", 0.9, "ru", "exa")

        results = db.get_results("q")
        assert len(results) == 1
        assert results[0]["title"] == "New"
        assert results[0]["language"] == "ru"


class TestMigration:
    def test_old_schema_is_migrated(self, tmp_db_path, monkeypatch):
        """A database created with the old global UNIQUE(url) must be rebuilt."""
        import sqlite3

        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)

        # Recreate the pre-migration schema.
        conn = sqlite3.connect(tmp_db_path)
        conn.executescript('''
            CREATE TABLE search_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                content TEXT,
                relevance_score REAL,
                language TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.execute(
            "INSERT INTO search_results (query, url, title) VALUES (?, ?, ?)",
            ("old query", "https://old.com", "Old"),
        )
        conn.commit()
        conn.close()

        db = Database()  # triggers the migration

        rows = db.get_results("old query")
        assert len(rows) == 1
        assert rows[0]["url"] == "https://old.com"

        # After the migration the same URL can be stored for another query.
        db.save_result("new query", "https://old.com", "Again", "c", 0.5, "ru", "exa")
        assert len(db.get_results("new query")) == 1

    def test_migration_is_idempotent(self, tmp_db_path, monkeypatch):
        import sqlite3

        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)

        Database()
        Database()  # must not fail on the already-migrated schema

        conn = sqlite3.connect(tmp_db_path)
        names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        conn.close()
        assert "search_results" in names
        assert "search_results_migrated" not in names


class TestSearchHistory:
    def test_save_history(self, tmp_db_path, monkeypatch):
        from config import Config
        monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
        db = Database()
        db.save_search_history("hello", "ru,en", 15)
        # No exception = success (we don't have a getter for history)
