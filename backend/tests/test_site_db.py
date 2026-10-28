"""Tests for backend.services.site_db.SiteDBService.

SiteDBService builds its own Database() instance, so Config.DATABASE_PATH must
be redirected before the service is constructed.
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.site_db import SiteDBService  # noqa: E402


@pytest.fixture()
def service(tmp_db_path, monkeypatch):
    from config import Config
    monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
    return SiteDBService()


class TestAddSite:
    def test_add_and_read_back(self, service):
        assert service.add_site("https://a.com", "Alpha", "news", "tag") is True
        sites = service.get_all_sites()
        assert len(sites) == 1
        assert sites[0]["url"] == "https://a.com"
        assert sites[0]["title"] == "Alpha"
        assert sites[0]["category"] == "news"
        assert sites[0]["tags"] == "tag"
        assert "id" in sites[0] and "added_at" in sites[0]

    def test_add_duplicate_url_kept_single(self, service):
        service.add_site("https://dup.com", "First")
        service.add_site("https://dup.com", "Second")
        assert len(service.get_all_sites()) == 1

    def test_add_returns_false_on_db_error(self, service):
        with patch.object(service.db, "add_custom_site", side_effect=RuntimeError("boom")):
            assert service.add_site("https://x.com", "X") is False


class TestGetAllSites:
    def test_empty(self, service):
        assert service.get_all_sites() == []

    def test_returns_empty_list_on_db_error(self, service):
        with patch.object(service.db, "get_custom_sites", side_effect=RuntimeError("boom")):
            assert service.get_all_sites() == []


class TestSearchInCustomDb:
    def test_matches_url(self, service):
        service.add_site("https://example.com/ai", "AI")
        found = service.search_in_custom_db("example.com")
        assert len(found) == 1

    def test_matches_title(self, service):
        service.add_site("https://x.com", "Interesting Title")
        found = service.search_in_custom_db("interesting")
        assert len(found) == 1

    def test_matches_tags(self, service):
        service.add_site("https://y.com", "Y", None, "python,machine learning")
        found = service.search_in_custom_db("machine")
        assert len(found) == 1

    def test_no_match_returns_empty(self, service):
        service.add_site("https://x.com", "X")
        assert service.search_in_custom_db("nothing-matches-this") == []

    def test_search_is_case_insensitive(self, service):
        service.add_site("https://x.com", "X")
        assert len(service.search_in_custom_db("X.COM")) == 1

    def test_none_tags_do_not_raise(self, service):
        """A site saved without tags must not break the tags comparison."""
        service.add_site("https://z.com", "Z")
        assert service.search_in_custom_db("z") is not None


class TestGetSiteUrls:
    def test_returns_urls(self, service):
        service.add_site("https://one.com", "One")
        service.add_site("https://two.com", "Two")
        assert set(service.get_site_urls()) == {"https://one.com", "https://two.com"}

    def test_empty(self, service):
        assert service.get_site_urls() == []


class TestDeleteSite:
    def test_delete_existing(self, service):
        service.add_site("https://del.com", "Del")
        site_id = service.get_all_sites()[0]["id"]
        assert service.delete_site(site_id) is True
        assert service.get_all_sites() == []

    def test_delete_missing_returns_false(self, service):
        assert service.delete_site(999999) is False

    def test_delete_returns_false_on_db_error(self, service):
        with patch.object(service.db, "delete_custom_site", side_effect=RuntimeError("boom")):
            assert service.delete_site(1) is False


class TestAddFromSearchResult:
    def test_uses_default_category(self, service):
        assert service.add_from_search_result("https://r.com", "Result") is True
        sites = service.get_all_sites()
        assert sites[0]["category"] == "search_result"
