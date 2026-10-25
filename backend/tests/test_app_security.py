"""Security-focused API tests: input validation, upload limits, error masking.

Reuses the mock-heavy fixtures from test_app_api so no network or model
loading happens here either.
"""

import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Reuse the fixtures (client / api_client) defined for the API test module.
from tests.test_app_api import client, api_client, tmp_db  # noqa: F401


# ── Request validation surfaces as 422, not a 500 later ────────────────────

@pytest.mark.asyncio
async def test_search_blank_query_returns_422(api_client):
    resp = await api_client.post("/api/search", json={"query": "   ", "languages": ["ru"]})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_missing_query_returns_422(api_client):
    resp = await api_client.post("/api/search", json={"languages": ["ru"]})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_unknown_language_returns_422(api_client):
    resp = await api_client.post("/api/search", json={"query": "ok", "languages": ["fr"]})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_num_results_too_large_returns_422(api_client):
    """Unbounded num_results is a cost/DoS vector against the Exa API."""
    resp = await api_client.post(
        "/api/search", json={"query": "ok", "languages": ["ru"], "num_results": 10000}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_num_results_at_bounds_accepted(api_client, client):
    mocks, _ = client
    mocks["translator"].translate_to_multiple.return_value = {"original": "ok", "ru": "ok"}
    mocks["exa_service"].search.return_value = []
    mocks["site_db_service"].get_site_urls.return_value = []
    mocks["site_db_service"].search_in_custom_db.return_value = []
    mocks["indexing_service"].rank_results.side_effect = lambda items, urls: items

    resp = await api_client.post(
        "/api/search", json={"query": "ok", "languages": ["ru"], "num_results": 50}
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ── Error responses must not leak internals ────────────────────────────────

@pytest.mark.asyncio
async def test_search_error_response_is_generic(api_client, client):
    mocks, _ = client
    mocks["translator"].translate_to_multiple.return_value = {"original": "q", "ru": "q"}
    mocks["exa_service"].search.side_effect = RuntimeError(
        "secret internal detail: /home/user/token.txt"
    )

    resp = await api_client.post("/api/search", json={"query": "q", "languages": ["ru"]})
    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"] == "Internal server error"
    assert "secret" not in resp.text
    assert "/home/user" not in resp.text


@pytest.mark.asyncio
async def test_add_site_error_response_is_generic(api_client, client):
    mocks, _ = client
    mocks["site_db_service"].add_site.side_effect = RuntimeError("sqlite path C:\\secrets")

    resp = await api_client.post(
        "/api/custom-sites/add", json={"url": "https://x.com", "title": "X"}
    )
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal server error"
    assert "secrets" not in resp.text


# ── Upload size limits ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ocr_oversized_body_rejected(api_client, monkeypatch):
    """The real body size must be enforced, not just the declared header."""
    from config import Config

    monkeypatch.setattr(Config, "MAX_UPLOAD_BYTES", 64)
    resp = await api_client.post(
        "/api/ocr",
        files={"file": ("big.pdf", b"x" * 4096, "application/pdf")},
    )
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ocr_malformed_content_length_returns_400(client):
    """A garbage Content-Length header must yield 400, not an unhandled 500."""
    mocks, app_mod = client

    class FakeUpload:
        filename = "doc.pdf"
        headers = {"content-length": "not-a-number"}

        async def read(self):
            return b"data"

    with pytest.raises(HTTPException) as exc:
        await app_mod.ocr_process(FakeUpload())
    assert exc.value.status_code == 400
    assert "Invalid Content-Length" in str(exc.value.detail)
