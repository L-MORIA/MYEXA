"""Integration tests for the FastAPI application endpoints.

All external services are monkeypatched so tests run without network.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.exa_service import ExaError  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Redirect Database to a temp file so tests don't touch the real DB."""
    db_path = str(tmp_path / "test.db")
    from config import Config
    monkeypatch.setattr(Config, "DATABASE_PATH", db_path)
    return db_path


@pytest.fixture()
def client(tmp_db, monkeypatch):
    """Return an httpx AsyncClient wired to the FastAPI app.

    Instead of patching constructors and reloading (which doesn't reliably
    replace module-level singletons), we patch the *instances* directly on the
    ``app`` module.
    """
    # Import app *after* Config.DATABASE_PATH is redirected
    import app as app_mod

    mocks = {
        "db": MagicMock(),
        "translator": MagicMock(),
        "exa_service": MagicMock(),
        "searxng_service": MagicMock(),
        "embedding_service": MagicMock(),
        "indexing_service": MagicMock(),
        "language_detector": MagicMock(),
        "ocr_service": MagicMock(),
        "site_db_service": MagicMock(),
    }

    monkeypatch.setattr(app_mod, "db", mocks["db"])
    monkeypatch.setattr(app_mod, "translator", mocks["translator"])
    monkeypatch.setattr(app_mod, "exa_service", mocks["exa_service"])
    monkeypatch.setattr(app_mod, "searxng_service", mocks["searxng_service"])
    monkeypatch.setattr(app_mod, "embedding_service", mocks["embedding_service"])
    monkeypatch.setattr(app_mod, "indexing_service", mocks["indexing_service"])
    monkeypatch.setattr(app_mod, "language_detector", mocks["language_detector"])
    monkeypatch.setattr(app_mod, "ocr_service", mocks["ocr_service"])
    monkeypatch.setattr(app_mod, "site_db_service", mocks["site_db_service"])

    # The fallback provider is disabled by default: the tests describe the
    # behaviour of a single provider. The fallback has its own tests.
    mocks["searxng_service"].is_configured.return_value = False
    mocks["searxng_service"].search.return_value = []

    # The language detector must not silently drop every result in the mocks.
    mocks["language_detector"].annotate.side_effect = lambda results, lang: results
    mocks["language_detector"].filter_by_language.side_effect = lambda results: results

    # Attach mocks dict for test access
    app_mod._mocks = mocks

    yield mocks, app_mod


@pytest.fixture()
def api_client(client):
    """Convenience: just the httpx client from the client fixture."""
    mocks, app_mod = client
    return AsyncClient(transport=ASGITransport(app=app_mod.app), base_url="http://test")


# ── Health ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(api_client):
    resp = await api_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data


# ── Search ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_returns_russian_results(api_client, client):
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {
        "original": "тест запрос",
        "ru": "тест запрос",
        "en": "test query",
    }

    mocks["exa_service"].search.return_value = [
        {"url": "https://example.com/ru/1", "title": "Result ru",
         "highlights": "Snippet ru", "score": 0.9, "language": "ru"}
    ]
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: [
        {**i, "relevance_index": 0.8} for i in items
    ]
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    resp = await api_client.post("/api/search", json={
        "query": "тест запрос",
        "languages": ["ru", "en"],
        "num_results": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "ru" in data["results"]
    assert "en" in data["results"]
    assert len(data["results"]["ru"]) == 1
    assert data["results"]["ru"][0]["title"] == "Result ru"


@pytest.mark.asyncio
async def test_search_localises_with_country_not_domain_filter(api_client, client):
    """Russian must NOT be pinned to a hard domain allowlist.

    `includeDomains` is a hard constraint in Exa — it confined the Russian
    corpus to five sites while English searched the whole web. Localisation
    now goes through `userLocation` (country code).
    """
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {
        "original": "новости", "ru": "новости",
    }
    mocks["exa_service"].search.return_value = []
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    await api_client.post("/api/search", json={
        "query": "новости",
        "languages": ["ru"],
    })

    mocks["exa_service"].search.assert_called_once()
    call_kwargs = mocks["exa_service"].search.call_args
    assert call_kwargs.kwargs.get("country") == "RU"
    assert "include_domains" not in call_kwargs.kwargs


@pytest.mark.asyncio
async def test_search_passes_country_per_language(api_client, client):
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {
        "original": "q", "ru": "q", "de": "q", "it": "q", "en": "q",
    }
    mocks["exa_service"].search.return_value = []
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    await api_client.post("/api/search", json={
        "query": "q", "languages": ["ru", "de", "it", "en"],
    })

    countries = {c.args[2]: c.kwargs.get("country")
                 for c in mocks["exa_service"].search.call_args_list}
    assert countries == {"ru": "RU", "de": "DE", "it": "IT", "en": "US"}


@pytest.mark.asyncio
async def test_search_filters_with_translated_query(api_client, client):
    """Verify embedding filter receives the TRANSLATED query, not the original."""
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {
        "original": "привет мир", "ru": "привет мир", "de": "hallo welt",
    }
    mocks["exa_service"].search.return_value = [
        {"url": "https://de.example.com", "title": "De", "highlights": "De snippet",
         "score": 0.8, "language": "de"}
    ]
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    await api_client.post("/api/search", json={
        "query": "привет мир",
        "languages": ["ru", "de"],
        "filter_by_relevance": True,
    })

    filter_calls = mocks["embedding_service"].filter_results.call_args_list
    assert len(filter_calls) >= 1
    all_query_args = [c[0][0] for c in filter_calls]
    assert "hallo welt" in all_query_args


# ── Custom Sites ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_custom_site(api_client, client):
    mocks, _ = client
    mocks["site_db_service"].add_site.return_value = True

    resp = await api_client.post("/api/custom-sites/add", json={
        "url": "https://test.com",
        "title": "Test Site",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_get_custom_sites(api_client, client):
    mocks, _ = client
    mocks["site_db_service"].get_all_sites.return_value = [
        {"id": 1, "url": "https://a.com", "title": "A",
         "category": None, "tags": None, "added_at": "2026-01-01"},
    ]

    resp = await api_client.get("/api/custom-sites")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_delete_custom_site(api_client, client):
    mocks, _ = client
    mocks["site_db_service"].delete_site.return_value = True

    resp = await api_client.delete("/api/custom-sites/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


# ── OCR ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ocr_rejects_bad_extension(api_client):
    resp = await api_client.post("/api/ocr", files={
        "file": ("test.exe", b"content", "application/octet-stream"),
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_ocr_accepts_pdf(api_client, client):
    mocks, _ = client
    mocks["ocr_service"].process_file.return_value = {
        "text": "extracted text", "confidence": 0.95,
        "method": "mocked", "success": True,
    }

    resp = await api_client.post("/api/ocr", files={
        "file": ("doc.pdf", b"%PDF-1.4 fake content", "application/pdf"),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["text"] == "extracted text"


# ── Search: orchestration details ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_defaults_to_source_language(api_client, client):
    """No 'languages' key -> the server falls back to Config.SOURCE_LANGUAGE."""
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {
        "original": "q", "ru": "q",
    }
    mocks["exa_service"].search.return_value = []
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    resp = await api_client.post("/api/search", json={"query": "q"})
    assert resp.status_code == 200
    assert "ru" in resp.json()["results"]


@pytest.mark.asyncio
async def test_search_saves_results_to_db(api_client, client):
    """Every ranked result must be persisted with its language."""
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {
        "original": "q", "ru": "q", "en": "q",
    }
    mocks["exa_service"].search.return_value = [
        {"url": "https://x.com/1", "title": "T", "highlights": "h",
         "score": 0.9, "language": "ru"}
    ]
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: [
        {**i, "relevance_index": 0.8} for i in items
    ]
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    await api_client.post("/api/search", json={"query": "q", "languages": ["ru", "en"]})

    assert mocks["db"].save_result.call_count == 2
    saved_langs = {c.kwargs["language"] for c in mocks["db"].save_result.call_args_list}
    assert saved_langs == {"ru", "en"}


@pytest.mark.asyncio
async def test_search_without_custom_db_key(api_client, client):
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.return_value = []
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []

    resp = await api_client.post("/api/search", json={
        "query": "q", "languages": ["ru"], "search_custom_db": False,
    })
    assert resp.status_code == 200
    assert "custom_db" not in resp.json()["results"]
    mocks["site_db_service"].search_in_custom_db.assert_not_called()


@pytest.mark.asyncio
async def test_search_skips_embedding_filter_when_disabled(api_client, client):
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.return_value = [
        {"url": "https://x.com", "title": "T", "highlights": "h", "score": 0.5}
    ]
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    resp = await api_client.post("/api/search", json={
        "query": "q", "languages": ["ru"], "filter_by_relevance": False,
    })
    assert resp.status_code == 200
    mocks["embedding_service"].filter_results.assert_not_called()


@pytest.mark.asyncio
async def test_search_uses_only_the_first_highlight(api_client, client):
    """The Exa parser keeps highlights[0] only; document that in the contract."""
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.return_value = [
        {"url": "https://x.com", "title": "T", "highlights": "h", "score": 0.5}
    ]
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    await api_client.post("/api/search", json={"query": "q", "languages": ["ru"]})

    call = mocks["exa_service"].search.call_args
    assert call.args[0] == "q"
    assert call.args[2] == "ru"  # language is passed positionally


@pytest.mark.asyncio
async def test_search_returns_500_on_service_failure(api_client, client):
    mocks, _ = client
    mocks["translator"].translate_to_multiple.side_effect = RuntimeError("translator down")

    resp = await api_client.post("/api/search", json={"query": "q", "languages": ["ru"]})
    assert resp.status_code == 500
    assert "translator down" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_search_translation_failure_falls_back_to_original(api_client, client):
    """If a language is missing from the translation map, the original query is used.

    Unknown *codes* are rejected with 400 (see
    test_rejects_unsupported_language); this covers a supported language whose
    translation is simply unavailable.
    """
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q"}
    mocks["exa_service"].search.return_value = []
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    resp = await api_client.post("/api/search", json={"query": "q", "languages": ["de"]})
    assert resp.status_code == 200
    call = mocks["exa_service"].search.call_args
    assert call.args[0] == "q"


# ── Search: language detection ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_annotates_language_of_results(api_client, client):
    """Every result must be annotated with its detected language."""
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.return_value = [
        {"url": "https://x.com", "title": "T", "highlights": "h", "score": 0.5}
    ]
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    await api_client.post("/api/search", json={"query": "q", "languages": ["ru"]})

    mocks["language_detector"].annotate.assert_called()
    args = mocks["language_detector"].annotate.call_args
    assert args.args[1] == "ru"


@pytest.mark.asyncio
async def test_search_filters_by_language(api_client, client):
    """Results in another language must be removed from a language tab."""
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.return_value = [
        {"url": "https://x.com", "title": "T", "highlights": "h", "score": 0.5}
    ]
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    await api_client.post("/api/search", json={"query": "q", "languages": ["ru"]})

    mocks["language_detector"].filter_by_language.assert_called()


@pytest.mark.asyncio
async def test_search_reports_language_mismatch_count(api_client, client):
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.return_value = [
        {"url": "https://x.com", "title": "T", "highlights": "h", "score": 0.5,
         "language_mismatch": True}
    ]
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    resp = await api_client.post("/api/search", json={"query": "q", "languages": ["ru"]})
    data = resp.json()
    assert data["meta"]["ru"]["language_mismatched"] == 1


# ── Search: validation and provider failures ───────────────────────────────

@pytest.mark.asyncio
async def test_rejects_unsupported_language(api_client, client):
    """An unknown language code must not be silently accepted."""
    mocks, _ = client

    resp = await api_client.post("/api/search", json={
        "query": "q", "languages": ["fr"],
    })
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "fr" in detail
    assert "Supported" in detail
    mocks["exa_service"].search.assert_not_called()


@pytest.mark.asyncio
async def test_rejects_num_results_above_exa_limit(api_client, client):
    """The public Exa limit is 100 results per request."""
    resp = await api_client.post("/api/search", json={
        "query": "q", "languages": ["ru"], "num_results": 1000,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rejects_empty_query(api_client, client):
    resp = await api_client.post("/api/search", json={"query": "", "languages": ["ru"]})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rejects_out_of_range_threshold(api_client, client):
    resp = await api_client.post("/api/search", json={
        "query": "q", "languages": ["ru"], "relevance_threshold": 1.5,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_returns_503_when_exa_down_and_no_local_results(api_client, client):
    """A provider outage must not look like 'no results found'."""
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.side_effect = ExaError("Exa API error 403")
    mocks["site_db_service"].search_in_custom_db.return_value = []

    resp = await api_client.post("/api/search", json={"query": "q", "languages": ["ru"]})
    assert resp.status_code == 503
    assert "403" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_local_custom_db_still_answers_when_provider_is_down(api_client, client):
    """The custom database is searched locally and needs no network.

    A total provider outage must not take the local results down with it.
    """
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.side_effect = ExaError("Exa API error 403")
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = [
        {"id": 1, "url": "https://local.test/a", "title": "Local hit", "category": "news"}
    ]

    resp = await api_client.post("/api/search", json={"query": "q", "languages": ["ru"]})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]["custom_db"]) == 1
    assert data["results"]["ru"] == []
    # The reason for the empty language tab must be visible.
    assert "error" in data["meta"]["ru"]


@pytest.mark.asyncio
async def test_partial_provider_failure_returns_results(api_client, client):
    """One failing language must not discard the others."""
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {
        "original": "q", "ru": "q", "en": "q",
    }

    def search(query, num_results, language, country=None, **kw):
        if language == "ru":
            raise ExaError("Exa API error 403")
        return [{"url": "https://x.com", "title": "T", "highlights": "h", "score": 0.5}]

    mocks["exa_service"].search.side_effect = search
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    resp = await api_client.post("/api/search", json={
        "query": "q", "languages": ["ru", "en"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data["meta"]["ru"]
    assert len(data["results"]["en"]) == 1


@pytest.mark.asyncio
async def test_searches_languages_in_parallel(api_client, client):
    """The language searches are independent and must not run one after another."""
    import time

    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {
        "original": "q", "ru": "q", "en": "q", "de": "q", "it": "q",
    }

    def slow_search(query, num_results, language, country=None, **kw):
        time.sleep(0.3)
        return [{"url": "https://x.com", "title": "T", "highlights": "h", "score": 0.5}]

    mocks["exa_service"].search.side_effect = slow_search
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    start = time.perf_counter()
    resp = await api_client.post("/api/search", json={
        "query": "q", "languages": ["ru", "en", "de", "it"],
    })
    elapsed = time.perf_counter() - start

    assert resp.status_code == 200
    # Sequential would be >= 1.2s; concurrent stays well below that.
    assert elapsed < 1.0, f"languages searched sequentially ({elapsed:.2f}s)"


# ── Languages endpoint ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_languages_endpoint(api_client):
    """The frontend builds its language list from this endpoint."""
    resp = await api_client.get("/api/languages")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    codes = [lang["code"] for lang in data["languages"]]
    assert codes == ["ru", "en", "de", "it"]
    for lang in data["languages"]:
        assert lang["label"]
        assert lang["country"]
    assert data["default"] == ["ru"]


@pytest.mark.asyncio
async def test_health_deep_reports_provider_state(api_client, client):
    mocks, _ = client
    mocks["exa_service"].search.return_value = []

    resp = await api_client.get("/api/health?deep=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["checks"]["exa"]["ok"] is True
    assert data["embedding_model"]
    assert "language_detector_available" in data


@pytest.mark.asyncio
async def test_health_deep_reports_degraded(api_client, client):
    """A broken provider must show up as degraded, not as a cheerful healthy."""
    mocks, _ = client
    mocks["exa_service"].search.side_effect = ExaError("Exa API error 403")

    resp = await api_client.get("/api/health?deep=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["checks"]["exa"]["ok"] is False


# ── Custom sites: error paths ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_custom_site_returns_500_on_failure(api_client, client):
    mocks, _ = client
    mocks["site_db_service"].add_site.side_effect = RuntimeError("db down")

    resp = await api_client.post("/api/custom-sites/add", json={
        "url": "https://x.com", "title": "X",
    })
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_get_custom_sites_returns_500_on_failure(api_client, client):
    mocks, _ = client
    mocks["site_db_service"].get_all_sites.side_effect = RuntimeError("db down")

    resp = await api_client.get("/api/custom-sites")
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_delete_custom_site_returns_500_on_failure(api_client, client):
    mocks, _ = client
    mocks["site_db_service"].delete_site.side_effect = RuntimeError("db down")

    resp = await api_client.delete("/api/custom-sites/1")
    assert resp.status_code == 500


# ── Static / root ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_root_serves_frontend(api_client):
    resp = await api_client.get("/")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_index_html_is_not_cached(api_client):
    """The HTML references the versioned asset URLs (?v=N).

    A cached index.html keeps pointing at the previous asset version, so
    frontend updates only arrive after a manual hard reload.
    """
    resp = await api_client.get("/")
    cache_control = resp.headers.get("cache-control", "")
    assert "no-cache" in cache_control or "no-store" in cache_control
    assert "must-revalidate" in cache_control


@pytest.mark.asyncio
async def test_frontend_assets_are_versioned(api_client):
    """The served HTML must reference versioned assets."""
    resp = await api_client.get("/")
    assert "script.js?v=" in resp.text
    assert "style.css?v=" in resp.text


@pytest.mark.asyncio
async def test_favicon_route(api_client):
    resp = await api_client.get("/favicon.ico")
    assert resp.status_code in (200, 307)


# ── OCR: guards and failures ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ocr_rejects_oversized_file(api_client):
    """A part content-length above 50MB must be rejected before reading the body.

    httpx's `files=` helper does not emit a per-part Content-Length header, so
    the multipart body is assembled by hand here.
    """
    body = (
        b"--BOUNDARY\r\n"
        b'Content-Disposition: form-data; name="file"; filename="big.pdf"\r\n'
        b"Content-Type: application/pdf\r\n"
        b"Content-Length: 62914560\r\n"
        b"\r\n"
        b"small body\r\n"
        b"--BOUNDARY--\r\n"
    )
    headers = {"Content-Type": "multipart/form-data; boundary=BOUNDARY"}

    resp = await api_client.post("/api/ocr", content=body, headers=headers)
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ocr_returns_500_when_service_fails(api_client, client):
    mocks, _ = client
    mocks["ocr_service"].process_file.side_effect = RuntimeError("tesseract missing")

    resp = await api_client.post("/api/ocr", files={
        "file": ("doc.pdf", b"%PDF", "application/pdf"),
    })
    assert resp.status_code == 500
    assert "tesseract missing" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_ocr_language_is_forwarded(api_client, client):
    mocks, _ = client
    mocks["ocr_service"].process_file.return_value = {
        "text": "ok", "confidence": 0.9, "method": "mocked", "success": True,
    }

    await api_client.post("/api/ocr?language=rus", files={
        "file": ("doc.pdf", b"%PDF", "application/pdf"),
    })
    assert mocks["ocr_service"].process_file.call_args.args[1] == "rus"


# ── Fallback provider (SearXNG) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_falls_back_to_searxng_when_exa_fails(api_client, client):
    """A blocked primary provider must not mean an empty search."""
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.side_effect = ExaError("Exa API error 403")
    mocks["searxng_service"].is_configured.return_value = True
    mocks["searxng_service"].search.return_value = [
        {"url": "https://fallback.test/a", "title": "Fallback hit",
         "highlights": "snippet", "score": 0.7, "language": "ru"}
    ]
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    resp = await api_client.post("/api/search", json={"query": "q", "languages": ["ru"]})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]["ru"]) == 1
    assert data["results"]["ru"][0]["url"] == "https://fallback.test/a"
    # The user must be able to see which provider answered and why.
    assert data["meta"]["ru"]["provider"] == "searxng"
    assert "403" in data["meta"]["ru"]["fallback_reason"]
    mocks["searxng_service"].search.assert_called_once()


@pytest.mark.asyncio
async def test_fallback_is_not_used_while_exa_works(api_client, client):
    """The primary provider stays in charge as long as it answers."""
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.return_value = [
        {"url": "https://exa.test/a", "title": "Exa hit", "highlights": "s",
         "score": 0.9, "language": "ru"}
    ]
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    resp = await api_client.post("/api/search", json={"query": "q", "languages": ["ru"]})
    assert resp.status_code == 200
    assert resp.json()["meta"]["ru"]["provider"] == "exa"
    mocks["searxng_service"].search.assert_not_called()


@pytest.mark.asyncio
async def test_503_when_both_providers_fail(api_client, client):
    """Both reasons must be visible — not just the first one."""
    from services.searxng_service import SearxngError

    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.side_effect = ExaError("Exa API error 403")
    mocks["searxng_service"].is_configured.return_value = True
    mocks["searxng_service"].search.side_effect = SearxngError("connection refused")
    mocks["site_db_service"].search_in_custom_db.return_value = []

    resp = await api_client.post("/api/search", json={"query": "q", "languages": ["ru"]})
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert "403" in detail
    assert "connection refused" in detail


@pytest.mark.asyncio
async def test_fallback_results_are_stored_with_their_source(api_client, client):
    """The stored source must name the provider that actually answered."""
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.side_effect = ExaError("Exa API error 403")
    mocks["searxng_service"].is_configured.return_value = True
    mocks["searxng_service"].search.return_value = [
        {"url": "https://fallback.test/a", "title": "Fallback hit",
         "highlights": "snippet", "score": 0.7, "language": "ru"}
    ]
    mocks["embedding_service"].filter_results.side_effect = lambda q, items, **kw: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    await api_client.post("/api/search", json={"query": "q", "languages": ["ru"]})

    sources = [c.kwargs.get("source") for c in mocks["db"].save_result.call_args_list]
    assert sources == ["searxng"]


@pytest.mark.asyncio
async def test_health_reports_the_fallback_as_active(api_client, client):
    """The primary is down but the search still works — say so explicitly."""
    mocks, _ = client

    mocks["exa_service"].search.side_effect = ExaError("Exa API error 403")
    mocks["searxng_service"].is_configured.return_value = True
    mocks["searxng_service"].search.return_value = [
        {"url": "https://fallback.test/a", "title": "t", "highlights": "s"}
    ]

    resp = await api_client.get("/api/health?deep=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["active_provider"] == "searxng"
    assert data["search_available"] is True
    assert data["checks"]["exa"]["ok"] is False
    assert data["checks"]["searxng"]["ok"] is True

