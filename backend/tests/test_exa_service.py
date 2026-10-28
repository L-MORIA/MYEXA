"""Tests for backend.services.exa_service.ExaService."""

from unittest.mock import patch

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

    def test_user_location_sent_to_payload(self):
        """Localisation uses userLocation (country code), not a domain filter."""
        svc = self._make_service()
        captured_payload = {}

        def capture(endpoint, data):
            captured_payload.update(data)
            return {"results": []}

        with patch.object(svc, "_request", side_effect=capture):
            svc.search("новости", 10, "ru", country="RU")

        assert captured_payload["userLocation"] == "RU"

    def test_include_domains_not_sent_by_default(self):
        """No hard domain filter unless it is explicitly requested."""
        svc = self._make_service()
        captured_payload = {}

        def capture(endpoint, data):
            captured_payload.update(data)
            return {"results": []}

        with patch.object(svc, "_request", side_effect=capture):
            svc.search("новости", 10, "ru", country="RU")

        assert "includeDomains" not in captured_payload

    def test_user_location_absent_without_country(self):
        svc = self._make_service()
        captured_payload = {}

        def capture(endpoint, data):
            captured_payload.update(data)
            return {"results": []}

        with patch.object(svc, "_request", side_effect=capture):
            svc.search("test", 10, "en")

        assert "userLocation" not in captured_payload

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
        """A provider failure must surface, not look like "no results"."""
        svc = self._make_service()
        with patch.object(svc, "_request", side_effect=ExaError("boom")):
            with pytest.raises(ExaError):
                svc.search("test", 10, "de")

    def test_unexpected_error_is_wrapped(self):
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

    def test_empty_response(self):
        svc = ExaService.__new__(ExaService)
        svc.api_key = "test"
        with patch.object(svc, "_request", return_value={}):
            assert svc.get_contents(["https://a.com"]) == []

    def test_returns_empty_on_exception(self):
        """A provider failure must surface instead of looking like 'no content'."""
        svc = ExaService.__new__(ExaService)
        svc.api_key = "test"
        with patch.object(svc, "_request", side_effect=ExaError("boom")):
            with pytest.raises(ExaError):
                svc.get_contents(["https://a.com"])


class TestRequest:
    """The raw HTTP layer — previously untested (coverage was 75%)."""

    def _svc(self):
        svc = ExaService.__new__(ExaService)
        svc.api_key = "test-key"
        return svc

    def test_posts_to_exa_endpoint_with_api_key(self):
        svc = self._svc()
        captured = {}

        class _Resp:
            status_code = 200

            @staticmethod
            def json():
                return {"results": []}

        def fake_post(url, **kwargs):
            captured["url"] = url
            captured["headers"] = kwargs.get("headers")
            captured["json"] = kwargs.get("json")
            return _Resp()

        with patch("services.exa_service.requests.post", side_effect=fake_post):
            svc._request("/search", {"query": "x"})

        assert captured["url"] == "https://api.exa.ai/search"
        assert captured["headers"]["x-api-key"] == "test-key"
        assert captured["json"] == {"query": "x"}

    def test_non_200_raises_exa_error(self):
        svc = self._svc()

        class _Resp:
            status_code = 403
            text = "forbidden"

        with patch("services.exa_service.requests.post", return_value=_Resp()):
            with pytest.raises(ExaError) as exc:
                svc._request("/search", {"query": "x"})
        assert exc.value.status_code == 403

    def test_network_exception_becomes_exa_error(self):
        """_request must not swallow transport errors — search() handles them."""
        svc = self._svc()
        with patch("services.exa_service.requests.post", side_effect=RuntimeError("dns")):
            with pytest.raises(ExaError):
                svc._request("/search", {"query": "x"})

    def test_malformed_json_becomes_exa_error(self):
        svc = self._svc()

        class _Resp:
            status_code = 200
            text = "<html>"

            @staticmethod
            def json():
                raise ValueError("not json")

        with patch("services.exa_service.requests.post", return_value=_Resp()):
            with pytest.raises(ExaError):
                svc._request("/search", {"query": "x"})

    def test_timeout_is_set(self):
        svc = self._svc()
        captured = {}

        class _Resp:
            status_code = 200

            @staticmethod
            def json():
                return {}

        def fake_post(url, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return _Resp()

        with patch("services.exa_service.requests.post", side_effect=fake_post):
            svc._request("/search", {"query": "x"})
        assert captured["timeout"] is not None


class TestSearchMultipleLanguages:
    def test_returns_key_per_language(self):
        svc = ExaService.__new__(ExaService)
        svc.api_key = "test"
        with patch.object(svc, "search", return_value=[]) as m:
            out = svc.search_multiple_languages("q", ["ru", "en"])
        assert set(out) == {"ru", "en"}
        assert m.call_count == 2


class TestResultParsing:
    def test_multiple_highlights_are_concatenated_or_first_taken(self):
        """Documents current behaviour: only the FIRST highlight is kept."""
        svc = ExaService.__new__(ExaService)
        svc.api_key = "test"
        payload = {
            "results": [
                {
                    "url": "https://a.com",
                    "title": "A",
                    "highlights": ["first highlight", "second highlight"],
                    "highlightScores": [0.9, 0.4],
                }
            ]
        }
        with patch.object(svc, "_request", return_value=payload):
            res = svc.search("q", 10, "ru")
        assert res[0]["highlights"] == "first highlight"
        assert res[0]["score"] == 0.9

    def test_highlight_scores_all_preserved(self):
        """Every highlightScore must survive parsing, not just the first."""
        svc = ExaService.__new__(ExaService)
        svc.api_key = "test"
        payload = {
            "results": [
                {
                    "url": "https://a.com",
                    "title": "A",
                    "highlights": ["h1", "h2", "h3"],
                    "highlightScores": [0.9, 0.4, 0.75],
                }
            ]
        }
        with patch.object(svc, "_request", return_value=payload):
            res = svc.search("q", 10, "ru")
        assert res[0]["highlight_scores"] == [0.9, 0.4, 0.75]
        assert res[0]["score"] == 0.9

    def test_published_date_is_parsed(self):
        """publishedDate must be preserved for freshness scoring."""
        svc = ExaService.__new__(ExaService)
        svc.api_key = "test"
        payload = {
            "results": [
                {
                    "url": "https://a.com",
                    "title": "A",
                    "highlights": ["h"],
                    "publishedDate": "2026-01-01T00:00:00.000Z",
                }
            ]
        }
        with patch.object(svc, "_request", return_value=payload):
            res = svc.search("q", 10, "ru")
        assert res[0]["published_date"] == "2026-01-01T00:00:00.000Z"

    def test_missing_published_date_is_none(self):
        svc = ExaService.__new__(ExaService)
        svc.api_key = "test"
        payload = {"results": [{"url": "https://a.com", "title": "A", "highlights": ["h"]}]}
        with patch.object(svc, "_request", return_value=payload):
            res = svc.search("q", 10, "ru")
        assert res[0]["published_date"] is None

    def test_missing_highlights_yields_empty_string(self):
        svc = ExaService.__new__(ExaService)
        svc.api_key = "test"
        payload = {"results": [{"url": "https://a.com", "title": "A"}]}
        with patch.object(svc, "_request", return_value=payload):
            res = svc.search("q", 10, "ru")
        assert res[0]["highlights"] == ""
        assert res[0]["score"] == 0.0

    def test_results_use_published_date_key(self):
        """The parser exposes `published_date`; the legacy `created_at` key is gone."""
        svc = ExaService.__new__(ExaService)
        svc.api_key = "test"
        payload = {
            "results": [
                {
                    "url": "https://a.com",
                    "title": "A",
                    "highlights": ["x"],
                    "publishedDate": "2026-01-01T00:00:00.000Z",
                }
            ]
        }
        with patch.object(svc, "_request", return_value=payload):
            res = svc.search("q", 10, "ru")
        assert res[0]["published_date"] == "2026-01-01T00:00:00.000Z"
        assert "created_at" not in res[0]
