"""Tests for backend.services.searxng_service.SearxngService."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.searxng_service import (  # noqa: E402
    SEARXNG_LANGUAGES,
    SearxngError,
    SearxngService,
)


class _Resp:
    def __init__(self, payload=None, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


# ── Configuration ───────────────────────────────────────────────────────────

class TestConfiguration:
    def test_disabled_by_config(self):
        with patch("services.searxng_service.Config.SEARXNG_ENABLED", False):
            assert SearxngService().is_configured() is False

    def test_enabled_with_a_url(self):
        with patch("services.searxng_service.Config.SEARXNG_ENABLED", True):
            assert SearxngService(base_url="http://127.0.0.1:8080").is_configured() is True

    def test_empty_url_is_not_configured(self):
        with patch("services.searxng_service.Config.SEARXNG_ENABLED", True):
            assert SearxngService(base_url="").is_configured() is False

    def test_search_refuses_when_disabled(self):
        with patch("services.searxng_service.Config.SEARXNG_ENABLED", False):
            with pytest.raises(SearxngError):
                SearxngService().search("q")

    def test_trailing_slash_is_stripped(self):
        svc = SearxngService(base_url="http://127.0.0.1:8080/")
        assert svc.base_url == "http://127.0.0.1:8080"


# ── Request handling ────────────────────────────────────────────────────────

class TestSearch:
    def test_transport_failure_raises(self):
        with patch("services.searxng_service.requests.get", side_effect=RuntimeError("dns")):
            with pytest.raises(SearxngError):
                SearxngService().search("q")

    def test_http_error_raises(self):
        with patch("services.searxng_service.requests.get",
                   return_value=_Resp(status_code=502, text="bad gateway")):
            with pytest.raises(SearxngError) as exc:
                SearxngService().search("q")
        assert "502" in str(exc.value)

    def test_malformed_body_raises(self):
        with patch("services.searxng_service.requests.get", return_value=_Resp(payload=None)):
            with pytest.raises(SearxngError):
                SearxngService().search("q")

    def test_request_parameters(self):
        captured = {}

        def fake_get(url, params=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            return _Resp(payload={"results": []})

        with patch("services.searxng_service.requests.get", fake_get):
            SearxngService().search("искусственный интеллект", language="ru")

        assert captured["url"].endswith("/search")
        assert captured["params"]["q"] == "искусственный интеллект"
        assert captured["params"]["format"] == "json"
        # The two-letter code is translated into a locale the engines understand.
        assert captured["params"]["language"] == "ru-RU"

    def test_all_supported_languages_have_a_locale(self):
        from config import Config

        for lang in Config.SUPPORTED_LANGUAGES:
            assert lang in SEARXNG_LANGUAGES

    def test_results_are_mapped_to_the_exa_format(self):
        payload = {
            "results": [{
                "url": "https://example.test/a",
                "title": "  Title  ",
                "content": "  Snippet  ",
                "engine": "brave",
                "score": 3,
                "publishedDate": "20.04.2024 0:00:00",
            }]
        }
        with patch("services.searxng_service.requests.get", return_value=_Resp(payload=payload)):
            results = SearxngService().search("q", language="ru")

        item = results[0]
        assert item["url"] == "https://example.test/a"
        assert item["title"] == "Title"
        assert item["highlights"] == "Snippet"
        assert item["language"] == "ru"
        assert item["engine"] == "brave"
        assert item["provider"] == "searxng"
        assert item["published_date"].startswith("2024-04-20")

    def test_num_results_limits_the_result_set(self):
        payload = {"results": [
            {"url": f"https://example.test/{i}", "title": f"T{i}", "content": "c",
             "engine": "brave", "score": 1}
            for i in range(30)
        ]}
        with patch("services.searxng_service.requests.get", return_value=_Resp(payload=payload)):
            results = SearxngService().search("q", num_results=5)
        assert len(results) == 5

    def test_empty_result_set_is_not_an_error(self):
        with patch("services.searxng_service.requests.get",
                   return_value=_Resp(payload={"results": []})):
            assert SearxngService().search("q") == []


# ── Date parsing ────────────────────────────────────────────────────────────

class TestDateParsing:
    @pytest.mark.parametrize("raw,expected", [
        ("20.04.2024 0:00:00", "2024-04-20"),
        ("17.09.2026 12:30:00", "2026-09-17"),
        ("01.01.2020", "2020-01-01"),
        ("2023-05-06 10:00:00", "2023-05-06"),
        ("2023-05-06", "2023-05-06"),
    ])
    def test_known_formats(self, raw, expected):
        parsed = SearxngService._parse_date(raw)
        assert parsed is not None
        assert parsed.startswith(expected)

    @pytest.mark.parametrize("raw", ["", None, "not a date", "31.02.2024"])
    def test_unparseable_values(self, raw):
        assert SearxngService._parse_date(raw) is None

    def test_parsed_date_is_usable_by_the_freshness_score(self):
        """A date in a local format must not fall back to the neutral 0.5."""
        from services.indexing import IndexingService

        iso = SearxngService._parse_date("20.04.2024 0:00:00")
        freshness = IndexingService()._calculate_freshness(iso)
        assert freshness != 0.5


# ── Score normalisation ─────────────────────────────────────────────────────

class TestScoreNormalization:
    def test_scores_are_scaled_per_engine(self):
        results = [
            {"engine": "brave", "score": 0.0},
            {"engine": "brave", "score": 0.0},
            {"engine": "brave", "score": 0.0},
            {"engine": "google cse", "score": 0.0},
            {"engine": "google cse", "score": 0.0},
        ]
        SearxngService._normalize_scores(results)
        # The best result of every engine is 1.0, the worst is 0.0 — the raw
        # values (3 for Brave, 0.4 for Google CSE) are not comparable.
        assert results[0]["score"] == 1.0
        assert results[1]["score"] == 0.5
        assert results[2]["score"] == 0.0
        assert results[3]["score"] == 1.0
        assert results[4]["score"] == 0.0

    def test_single_result_of_an_engine_gets_a_full_score(self):
        results = [{"engine": "brave", "score": 0.0}]
        SearxngService._normalize_scores(results)
        assert results[0]["score"] == 1.0

    def test_scores_stay_within_the_unit_interval(self):
        payload = {"results": [
            {"url": "u", "title": "t", "content": "c", "engine": "brave", "score": 3}
        ]}
        with patch("services.searxng_service.requests.get", return_value=_Resp(payload=payload)):
            results = SearxngService().search("q")
        assert all(0.0 <= r["score"] <= 1.0 for r in results)
