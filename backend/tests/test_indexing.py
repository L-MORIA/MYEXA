"""Tests for backend.services.indexing.IndexingService."""

from datetime import datetime, timedelta, timezone

import pytest

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


class TestIndexScale:
    """Regression: weights were divided by 100 twice, collapsing the index
    to a 0-1 scale while the docstring/API promise 0-100."""

    def setup_method(self):
        self.svc = IndexingService()

    def test_perfect_result_scores_100(self):
        from datetime import datetime, timedelta, timezone
        result = {
            "url": "https://github.com/org/repo",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "embedding_score": 1.0,
        }
        score = self.svc.calculate_index(result, custom_sites=[result["url"]])
        assert score == pytest.approx(100.0)

    def test_embedding_score_changes_index_by_full_weight(self):
        recent_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        high = {"url": "https://x.com", "created_at": recent_iso, "embedding_score": 0.9}
        low = {"url": "https://x.com", "created_at": recent_iso, "embedding_score": 0.1}
        diff = self.svc.calculate_index(high) - self.svc.calculate_index(low)
        # 0.8 * 40 = 32 points — was 0.32 before the fix
        assert diff == pytest.approx(32.0)

    def test_baseline_index_is_substantive(self):
        """A mediocre result must still land in the tens, not at ~0.5."""
        result = {"url": "https://example.com", "created_at": None}
        score = self.svc.calculate_index(result)
        assert 30.0 < score < 100.0


class TestDomainAuthorityHardening:
    """Regression: substring matching let attackers spoof trusted domains."""

    def setup_method(self):
        self.svc = IndexingService()

    def test_exact_trusted_domain(self):
        assert self.svc._calculate_domain_authority("https://github.com/user/repo") == 1.0

    def test_subdomain_of_trusted_domain(self):
        assert self.svc._calculate_domain_authority("https://gist.github.com/x") == 1.0

    def test_docs_subdomain_trusted(self):
        assert self.svc._calculate_domain_authority("https://docs.python.org/3/") == 1.0

    def test_lookalike_host_not_trusted(self):
        assert self.svc._calculate_domain_authority("https://github.com.evil.example/x") == 0.7

    def test_trusted_name_in_path_not_trusted(self):
        assert self.svc._calculate_domain_authority("https://evil.example/github.com") == 0.7

    def test_trusted_name_in_query_not_trusted(self):
        url = "https://evil.example/?redirect=stackoverflow.com"
        assert self.svc._calculate_domain_authority(url) == 0.7

    def test_schemeless_url_parsed_correctly(self):
        assert self.svc._calculate_domain_authority("github.com/user/repo") == 1.0
        assert self.svc._calculate_domain_authority("evil.example/github.com") == 0.5

    def test_empty_url_gets_default(self):
        assert self.svc._calculate_domain_authority("") == 0.5


class TestFreshnessRobustness:
    def setup_method(self):
        self.svc = IndexingService()

    def test_invalid_date_returns_mid(self):
        assert self.svc._calculate_freshness("not-a-date") == 0.5

    def test_none_returns_mid(self):
        assert self.svc._calculate_freshness(None) == 0.5

    def test_wrong_type_returns_mid(self):
        assert self.svc._calculate_freshness(12345) == 0.5
