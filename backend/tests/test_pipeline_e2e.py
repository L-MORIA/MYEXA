"""End-to-end test of the whole search pipeline against a stub Exa API.

Exa's API host is unreachable from some networks (Cloudflare answers 403 for
the whole `api.exa.ai` hostname for certain IP ranges). That is an
environment problem, not a code problem — but it makes it impossible to
verify the pipeline end to end.

This test runs the real pipeline against a local stub that speaks Exa's
response format:

    translation -> Exa search -> relevance filter -> language detection
    -> language filter -> ranking

Only the HTTP layer of Exa is replaced. The embedding model, the language
detector and the ranking all run for real.
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from relevance_corpus import CORPUS  # noqa: E402


class _StubHandler(BaseHTTPRequestHandler):
    """Answers /search like Exa does, using the labelled corpus."""

    received_payloads = []

    def log_message(self, *args):  # silence the default stderr logging
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        _StubHandler.received_payloads.append(payload)

        results = []
        for item in CORPUS["en"]["items"]:
            results.append({
                "url": "https://example.com/" + item["title"][:24].replace(" ", "-"),
                "title": item["title"],
                "highlights": [item["highlights"]],
                "highlightScores": [0.8 if item["relevant"] else 0.4],
                "publishedDate": "2026-10-01T00:00:00.000Z",
            })

        body = json.dumps({"results": results}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def stub_server():
    server = HTTPServer(("127.0.0.1", 0), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture()
def patched_exa(stub_server, monkeypatch):
    from config import Config
    from services.exa_service import ExaService

    _StubHandler.received_payloads.clear()
    monkeypatch.setattr(Config, "EXA_API_URL", stub_server)
    monkeypatch.setattr(Config, "EXA_API_KEY", "stub-key")
    return ExaService()


class TestPipelineEndToEnd:
    def test_search_returns_results_through_the_full_pipeline(self, patched_exa):
        """With a reachable provider the pipeline produces ranked results."""
        results = patched_exa.search("test query", 10, "en", country="US")
        assert len(results) == 8
        assert results[0]["title"]
        assert results[0]["published_date"] == "2026-10-01T00:00:00.000Z"
        assert results[0]["score"] == 0.8

    def test_payload_carries_localisation_not_domain_filter(self, patched_exa):
        """Localisation must travel as userLocation, never as includeDomains."""
        patched_exa.search("test query", 10, "ru", country="RU")
        payload = _StubHandler.received_payloads[-1]
        assert payload["userLocation"] == "RU"
        assert "includeDomains" not in payload

    def test_relevance_filter_keeps_topical_results(self, patched_exa):
        """The real embedding filter must keep the relevant items."""
        from services.embedding import EmbeddingService

        svc = EmbeddingService()
        if not svc._available:
            pytest.skip("embedding model unavailable")

        results = patched_exa.search("artificial intelligence in medicine", 10, "en")
        kept = svc.filter_results("artificial intelligence in medicine", results)
        assert kept, "the filter must not empty a relevant result set"

        relevant = {i["title"] for i in CORPUS["en"]["items"] if i["relevant"]}
        kept_relevant = [k for k in kept if k["title"] in relevant]
        assert kept_relevant, "relevant results must survive the filter"

    def test_language_detection_annotates_results(self, patched_exa):
        from services.language_detector import LanguageDetector

        detector = LanguageDetector()
        if not detector.available:
            pytest.skip("lingua unavailable")

        results = patched_exa.search("test", 10, "en")
        detector.annotate(results, "en")
        assert all("language_match" in r for r in results)
        assert all(r["detected_language"] == "en" for r in results)

    def test_ranking_produces_indices_in_range(self, patched_exa):
        from services.indexing import IndexingService

        svc = IndexingService()
        results = patched_exa.search("test", 10, "en")
        ranked = svc.rank_results(results, [])
        assert ranked
        for item in ranked:
            assert 0.0 <= item["relevance_index"] <= 1.0
