"""Inspect the live MYEXA database schema and trigger the migration.

Run: python diagnostics/db_inspect.py
"""

import os
import sqlite3
import sys

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database", "myexa.db")
DB = os.path.normpath(DB)


def dump(label):
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='search_results'"
    ).fetchone()
    print(f"--- {label} ---")
    print(row[0] if row else "(no search_results table)")
    try:
        print("rows:", conn.execute("SELECT COUNT(*) FROM search_results").fetchone()[0])
        print("distinct urls:", conn.execute("SELECT COUNT(DISTINCT url) FROM search_results").fetchone()[0])
        print("distinct queries:", conn.execute("SELECT COUNT(DISTINCT query) FROM search_results").fetchone()[0])
    except sqlite3.Error as e:
        print("query error:", e)
    conn.close()
    print()


if not os.path.exists(DB):
    print(f"no database at {DB}")
    sys.exit(0)

dump("BEFORE migration")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from api.database import Database  # noqa: E402

Database()  # triggers init_db() -> _migrate_search_results()

dump("AFTER migration")

conn = sqlite3.connect(DB)
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
conn.close()
print("tables:", tables)
print("leftover migration table:", "search_results_migrated" in tables)
