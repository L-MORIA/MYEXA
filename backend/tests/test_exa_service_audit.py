"""Tests for backend.services.exa_service.ExaService."""

from unittest.mock import MagicMock, patch

import pytest
from services.exa_service import ExaError, ExaService


class TestExaServiceInit:
    def test_warns_on_empty_key(self, caplog):
        with patch("services.exa_service.Config.EXA_API_KEY", ""):
            ExaService()
            assert "EXA_API_KEY is empty" in caplog.text

    def test_stores_api_key(self):
        with patch("services.exa_service.Config.EXA_API_KEY", "test-key-123"):
            svc = ExaService()
            assert svc.api_key == "test-key-123"


class TestSearch:
    def _make_service(self, api_key="test-key"):
        with patch("services.exa_service.Config.EXA_API_KEY", api_key):
            return ExaService()

    def test_parses_results(self):
        svc = self._make_service()
        fake_response = {
            "results": [
                {"url": "https://a.com", "title": "A", "highlights": ["snippet A"], "highlightScores": [0.9]},
                {"url": "https://b.com", "title": "B", "highlights": ["snippet B"], "highlightScores": [0.5]},
            ]
        }
        with patch.object(svc, "_request", return_value=fake_response):
            results = svc.search("test", 10, "en")
        assert len(results) == 2
        assert results[0]["url"] == "https://a.com"
        assert results[0]["language"] == "en"
        assert results[0]["highlights"] == "snippet A"

    def test_empty_response(self):
        svc = self._make_service()
        with patch.object(svc, "_request", return_value={}):
            results = svc.search("test", 10, "ru")
        assert results == []

    def test_include_domains_passed_to_payload(self):
        """When include_domains is provided, it must appear in the API payload."""
        svc = self._make_service()
        captured_payload = {}

        def capture(endpoint, data):
            captured_payload.update(data)
            return {"results": []}

        with patch.object(svc, "_request", side_effect=capture):
            svc.search("тест", 10, "ru", include_domains=["lenta.ru", "habr.com"])

        assert "includeDomains" in captured_payload
        assert "lenta.ru" in captured_payload["includeDomains"]

    def test_no_include_domains_when_empty(self):
        """When include_domains is empty/None, payload must not contain the key."""
        svc = self._make_service()
        captured_payload = {}

        def capture(endpoint, data):
            captured_payload.update(data)
            return {"results": []}

        with patch.object(svc, "_request", side_effect=capture):
            svc.search("test", 10, "en")

        assert "includeDomains" not in captured_payload

    def test_returns_empty_on_exception(self):
        """A transport failure must not look like 'nothing found'.

        The exception is raised as ExaError so the caller can tell the two
        apart and fall back to another provider.
        """
        svc = self._make_service()
        with patch.object(svc, "_request", side_effect=RuntimeError("network down")):
            with pytest.raises(ExaError):
                svc.search("test", 10, "de")

    def test_empty_api_key_still_works(self):
        """Even with no key the method should not crash (returns [])."""
        svc = self._make_service(api_key="")
        # _request will get a non-200 because key is invalid
        with patch.object(svc, "_request", return_value={}):
            results = svc.search("test", 10, "en")
        assert results == []


class TestGetContents:
    def test_parses_contents(self):
        svc = ExaService.__new__(ExaService)
        svc.api_key = "test"
        fake_response = {
            "results": [
                {"url": "https://a.com", "title": "A", "text": "full text A"},
            ]
        }
        with patch.object(svc, "_request", return_value=fake_response):
            contents = svc.get_contents(["https://a.com"])
        assert len(contents) == 1
        assert contents[0]["text"] == "full text A"
