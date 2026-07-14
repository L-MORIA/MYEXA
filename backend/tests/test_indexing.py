"""Tests for backend.services.indexing.IndexingService."""

from datetime import datetime, timedelta, timezone

from services.indexing import IndexingService


class TestCalculateIndex:
    def setup_method(self):
        self.svc = IndexingService()

    def test_trusted_domain_gets_high_score(self):
        result = {"url": "https://github.com/example/repo", "created_at": None}
        score = self.svc.calculate_index(result)
        # github.com is trusted → domain_authority = 1.0 → contributes 20/100
        assert score > 0
        # A trusted domain should score more than a non-trusted, non-https one
        untrusted = {"url": "http://random.xyz", "created_at": None}
        assert score > self.svc.calculate_index(untrusted)

    def test_https_gets_more_than_http(self):
        https_result = {"url": "https://example.com", "created_at": None}
        http_result = {"url": "http://example.com", "created_at": None}
        assert self.svc.calculate_index(https_result) > self.svc.calculate_index(http_result)

    def test_custom_boost(self):
        result = {"url": "https://custom.com/page", "created_at": None}
        without_boost = self.svc.calculate_index(result, custom_sites=[])
        with_boost = self.svc.calculate_index(result, custom_sites=["https://custom.com/page"])
        assert with_boost > without_boost

    def test_freshness_recent(self):
        recent = {"url": "https://x.com", "created_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()}
        old = {"url": "https://x.com", "created_at": (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()}
        assert self.svc.calculate_index(recent) > self.svc.calculate_index(old)

    def test_freshness_none_returns_mid(self):
        result = {"url": "https://x.com", "created_at": None}
        score = self.svc.calculate_index(result)
        # freshness=0.5 → contributes 15 * 0.5 = 7.5
        assert score > 0

    def test_max_is_100(self):
        result = {
            "url": "https://github.com/org/repo",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "embedding_score": 1.0,
        }
        score = self.svc.calculate_index(result, custom_sites=[result["url"]])
        assert score <= 100.0

    def test_min_is_zero(self):
        result = {"url": "", "created_at": None, "embedding_score": 0.0}
        score = self.svc.calculate_index(result)
        assert score >= 0.0


class TestRankResults:
    def setup_method(self):
        self.svc = IndexingService()

    def test_sorts_descending(self):
        results = [
            {"url": "https://a.com", "embedding_score": 0.1},
            {"url": "https://github.com/x", "embedding_score": 0.9},
        ]
        ranked = self.svc.rank_results(results)
        # github.com gets domain authority boost + higher embedding
        assert ranked[0]["url"] == "https://github.com/x"

    def test_adds_relevance_index(self):
        results = [{"url": "https://a.com", "embedding_score": 0.5}]
        ranked = self.svc.rank_results(results)
        assert "relevance_index" in ranked[0]
