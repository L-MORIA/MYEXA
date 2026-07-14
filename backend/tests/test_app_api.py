"""Integration tests for the FastAPI application endpoints.

All external services are monkeypatched so tests run without network.
"""

import os
import sys
import tempfile

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
        "embedding_service": MagicMock(),
        "indexing_service": MagicMock(),
        "ocr_service": MagicMock(),
        "site_db_service": MagicMock(),
    }

    monkeypatch.setattr(app_mod, "db", mocks["db"])
    monkeypatch.setattr(app_mod, "translator", mocks["translator"])
    monkeypatch.setattr(app_mod, "exa_service", mocks["exa_service"])
    monkeypatch.setattr(app_mod, "embedding_service", mocks["embedding_service"])
    monkeypatch.setattr(app_mod, "indexing_service", mocks["indexing_service"])
    monkeypatch.setattr(app_mod, "ocr_service", mocks["ocr_service"])
    monkeypatch.setattr(app_mod, "site_db_service", mocks["site_db_service"])

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
    mocks["embedding_service"].filter_results.side_effect = lambda q, items: items
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
async def test_search_calls_exa_with_domains(api_client, client):
    mocks, _ = client

    mocks["translator"].translate_to_multiple.return_value = {
        "original": "новости", "ru": "новости",
    }
    mocks["exa_service"].search.return_value = []
    mocks["embedding_service"].filter_results.side_effect = lambda q, items: items
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []

    await api_client.post("/api/search", json={
        "query": "новости",
        "languages": ["ru"],
    })

    mocks["exa_service"].search.assert_called_once()
    call_kwargs = mocks["exa_service"].search.call_args
    assert "include_domains" in call_kwargs.kwargs
    domains = call_kwargs.kwargs["include_domains"]
    assert len(domains) > 0
    assert "lenta.ru" in domains


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
    mocks["embedding_service"].filter_results.side_effect = lambda q, items: items
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
