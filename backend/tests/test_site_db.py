"""Tests for backend.services.site_db.SiteDBService.

Focus: word-by-word custom-DB matching with ranking by hit count
(previously the whole query phrase had to be a substring, so real
multi-word queries never matched anything).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from services.site_db import SiteDBService


@pytest.fixture()
def svc(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "DATABASE_PATH", str(tmp_path / "sites.db"))
    return SiteDBService()


@pytest.fixture()
def seeded(svc):
    svc.add_site("https://docs.python.org/3/", "Python Docs", "docs", "python,reference")
    svc.add_site("https://fastapi.tiangolo.com/async/", "FastAPI Async", "docs", "python,async,web")
    svc.add_site("https://www.postgresql.org/", "PostgreSQL", "database", "sql,database")
    return svc


class TestWordMatching:
    def test_single_word_still_matches(self, seeded):
        results = seeded.search_in_custom_db("python")
        urls = {r["url"] for r in results}
        assert "https://docs.python.org/3/" in urls
        assert "https://fastapi.tiangolo.com/async/" in urls

    def test_multi_word_query_matches_partial_hits(self, seeded):
        """The regression case: whole-phrase matching returned nothing."""
        results = seeded.search_in_custom_db("python async programming")
        urls = {r["url"] for r in results}
        assert "https://docs.python.org/3/" in urls       # matches "python"
        assert "https://fastapi.tiangolo.com/async/" in urls  # matches "python"+"async"

    def test_no_match_returns_empty(self, seeded):
        assert seeded.search_in_custom_db("kubernetes rust wasm") == []

    def test_matching_is_case_insensitive(self, seeded):
        results = seeded.search_in_custom_db("PYTHON DOCS")
        assert any(r["url"] == "https://docs.python.org/3/" for r in results)

    def test_word_matched_in_url_title_or_tags(self, seeded):
        # "postgresql" is in url+title but not tags; "sql" only in tags
        results = seeded.search_in_custom_db("sql")
        assert any(r["url"] == "https://www.postgresql.org/" for r in results)


class TestRanking:
    def test_more_matched_words_rank_first(self, seeded):
        results = seeded.search_in_custom_db("python async")
        assert results[0]["url"] == "https://fastapi.tiangolo.com/async/"
        assert results[0]["match_count"] == 2
        assert results[1]["match_count"] == 1

    def test_match_count_field_exposed(self, seeded):
        results = seeded.search_in_custom_db("python")
        assert all("match_count" in r for r in results)


class TestQueryEdgeCases:
    def test_only_short_words_returns_empty(self, seeded):
        # 1-char words are noise ("c" is a substring of "docs") — skipped
        assert seeded.search_in_custom_db("a i c") == []

    def test_empty_query_returns_empty(self, seeded):
        assert seeded.search_in_custom_db("") == []

    def test_whitespace_query_returns_empty(self, seeded):
        assert seeded.search_in_custom_db("   ") == []

    def test_duplicate_words_counted_once(self, seeded):
        results = seeded.search_in_custom_db("python python python")
        assert results[0]["match_count"] == 1


class TestCrudDelegation:
    def test_add_and_get_all(self, svc):
        assert svc.add_site("https://x.com", "X") is True
        sites = svc.get_all_sites()
        assert len(sites) == 1
        assert sites[0]["url"] == "https://x.com"

    def test_get_site_urls(self, seeded):
        urls = seeded.get_site_urls()
        assert "https://www.postgresql.org/" in urls

    def test_delete_site(self, svc):
        svc.add_site("https://del.com", "Del")
        site_id = svc.get_all_sites()[0]["id"]
        assert svc.delete_site(site_id) is True
        assert svc.get_all_sites() == []
