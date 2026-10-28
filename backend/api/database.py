import os
import sqlite3
from contextlib import contextmanager

from config import Config


class Database:
    def __init__(self):
        self.db_path = Config.DATABASE_PATH
        # A fresh clone has no database directory yet — without this the
        # first start crashed with "unable to open database file".
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self):
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS search_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT,
                    content TEXT,
                    relevance_score REAL,
                    language TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(query, url)
                );
                CREATE TABLE IF NOT EXISTS custom_sites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    category TEXT,
                    tags TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    languages TEXT,
                    results_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_search_results_query
                    ON search_results(query);
            ''')
        self._migrate_search_results()

    def _migrate_search_results(self):
        """Rebuild `search_results` when it still carries the old global
        UNIQUE(url) constraint.

        With UNIQUE(url) a page found for a second query was silently dropped,
        so the stored result belonged to the first query only and the history
        of the second query lost the hit entirely.
        """
        with self._connect() as conn:
            columns = conn.execute("PRAGMA table_info(search_results)").fetchall()
            if not columns:
                return

            unique_on_url_only = False
            for index in conn.execute("PRAGMA index_list(search_results)").fetchall():
                if not index["unique"]:
                    continue
                index_columns = [
                    row["name"]
                    for row in conn.execute(f"PRAGMA index_info('{index['name']}')").fetchall()
                ]
                if index_columns == ["url"]:
                    unique_on_url_only = True
                    break

            if not unique_on_url_only:
                return

            conn.executescript('''
                CREATE TABLE search_results_migrated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT,
                    content TEXT,
                    relevance_score REAL,
                    language TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(query, url)
                );
                INSERT OR IGNORE INTO search_results_migrated
                    (id, query, url, title, content, relevance_score, language, source, created_at)
                    SELECT id, query, url, title, content, relevance_score, language, source, created_at
                    FROM search_results;
                DROP TABLE search_results;
                ALTER TABLE search_results_migrated RENAME TO search_results;
            ''')

    def save_result(self, query: str, url: str, title: str, content: str,
                   relevance_score: float, language: str, source: str):
        with self._connect() as conn:
            try:
                conn.execute('''
                    INSERT INTO search_results
                    (query, url, title, content, relevance_score, language, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(query, url) DO UPDATE SET
                        title = excluded.title,
                        content = excluded.content,
                        relevance_score = excluded.relevance_score,
                        language = excluded.language
                ''', (query, url, title, content, relevance_score, language, source))
            except sqlite3.IntegrityError:
                pass

    def get_results(self, query: str, limit: int = 50) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute('''
                SELECT * FROM search_results
                WHERE query = ?
                ORDER BY relevance_score DESC
                LIMIT ?
            ''', (query, limit)).fetchall()

    def add_custom_site(self, url: str, title: str, category: str = None, tags: str = None):
        with self._connect() as conn:
            try:
                conn.execute('''
                    INSERT INTO custom_sites (url, title, category, tags)
                    VALUES (?, ?, ?, ?)
                ''', (url, title, category, tags))
            except sqlite3.IntegrityError:
                pass

    def get_custom_sites(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute('SELECT * FROM custom_sites').fetchall()

    def save_search_history(self, query: str, languages: str, results_count: int):
        with self._connect() as conn:
            conn.execute('''
                INSERT INTO search_history (query, languages, results_count)
                VALUES (?, ?, ?)
            ''', (query, languages, results_count))

    def delete_custom_site(self, site_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute('DELETE FROM custom_sites WHERE id = ?', (site_id,))
            return cursor.rowcount > 0
