"""Tests for backend.services.indexing.IndexingService."""

from datetime import UTC, datetime, timedelta

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
        recent = {"url": "https://x.com", "created_at": (datetime.now(UTC) - timedelta(days=3)).isoformat()}
        old = {"url": "https://x.com", "created_at": (datetime.now(UTC) - timedelta(days=400)).isoformat()}
        assert self.svc.calculate_index(recent) > self.svc.calculate_index(old)

    def test_freshness_none_returns_mid(self):
        result = {"url": "https://x.com", "created_at": None}
        score = self.svc.calculate_index(result)
        # freshness=0.5 → contributes 15 * 0.5 = 7.5
        assert score > 0

    def test_max_is_100(self):
        result = {
            "url": "https://github.com/org/repo",
            "created_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "embedding_score": 1.0,
        }
        score = self.svc.calculate_index(result, custom_sites=[result["url"]])
        assert score <= 100.0

    def test_min_is_zero(self):
        result = {"url": "", "created_at": None, "embedding_score": 0.0}
        score = self.svc.calculate_index(result)
        assert score >= 0.0


class TestFreshnessBranches:
    def setup_method(self):
        self.svc = IndexingService()

    def _age(self, days):
        return (datetime.now(UTC) - timedelta(days=days)).isoformat()

    def test_under_week_is_max(self):
        assert self.svc._calculate_freshness(self._age(3)) == 1.0

    def test_under_month(self):
        assert self.svc._calculate_freshness(self._age(15)) == 0.8

    def test_under_quarter(self):
        assert self.svc._calculate_freshness(self._age(60)) == 0.6

    def test_under_year(self):
        assert self.svc._calculate_freshness(self._age(200)) == 0.4

    def test_over_year(self):
        assert self.svc._calculate_freshness(self._age(500)) == 0.2

    def test_invalid_date_returns_mid(self):
        assert self.svc._calculate_freshness("not-a-date") == 0.5

    def test_z_suffix_is_handled(self):
        assert self.svc._calculate_freshness("2026-10-25T00:00:00Z") in (0.2, 0.4, 0.6, 0.8, 1.0)

    def test_naive_datetime_is_treated_as_utc(self):
        assert self.svc._calculate_freshness("2026-10-25T00:00:00") in (0.2, 0.4, 0.6, 0.8, 1.0)

    def test_published_date_is_used_for_freshness(self):
        """The Exa publication date must feed the freshness component."""
        svc = IndexingService()
        fresh = {"url": "https://a.com", "published_date": self._age(2)}
        old = {"url": "https://a.com", "published_date": self._age(400)}
        assert svc.calculate_index(fresh) > svc.calculate_index(old)

    def test_created_at_still_supported_as_fallback(self):
        """`created_at` keeps working as a fallback for the publication date."""
        svc = IndexingService()
        with_date = svc.calculate_index({"url": "https://a.com", "created_at": self._age(2)})
        without_date = svc.calculate_index({"url": "https://a.com"})
        assert with_date > without_date

    def test_published_date_takes_precedence_over_created_at(self):
        svc = IndexingService()
        result = {
            "url": "https://a.com",
            "published_date": self._age(400),
            "created_at": self._age(1),
        }
        stale = svc.calculate_index(result)
        fresh = svc.calculate_index({"url": "https://a.com", "published_date": self._age(1)})
        assert fresh > stale


class TestDomainAuthorityPerLanguage:
    """Regression: the old trusted-domain list was English-only, so every
    Russian result was systematically penalised in the ranking."""

    def setup_method(self):
        self.svc = IndexingService()

    def test_russian_domains_are_trusted(self):
        assert self.svc._calculate_domain_authority("https://lenta.ru/news/x", "ru") == 1.0
        assert self.svc._calculate_domain_authority("https://kommersant.ru/doc/1", "ru") == 1.0
        assert self.svc._calculate_domain_authority("https://expert.ru/x", "ru") == 1.0

    def test_german_domains_are_trusted(self):
        assert self.svc._calculate_domain_authority("https://www.spiegel.de/a/x", "de") == 1.0
        assert self.svc._calculate_domain_authority("https://www.golem.de/x", "de") == 1.0

    def test_italian_domains_are_trusted(self):
        assert self.svc._calculate_domain_authority("https://www.repubblica.it/x", "it") == 1.0
        assert self.svc._calculate_domain_authority("https://www.corriere.it/x", "it") == 1.0

    def test_global_domains_are_trusted_in_every_language(self):
        for lang in ("ru", "en", "de", "it"):
            assert self.svc._calculate_domain_authority("https://github.com/x/y", lang) == 1.0
            assert self.svc._calculate_domain_authority("https://arxiv.org/abs/1", lang) == 1.0

    def test_local_wikipedia_is_trusted(self):
        for host, lang in (("ru.wikipedia.org", "ru"), ("de.wikipedia.org", "de"),
                           ("it.wikipedia.org", "it")):
            assert self.svc._calculate_domain_authority(f"https://{host}/x", lang) == 1.0

    def test_russian_result_no_longer_penalised_vs_english(self):
        """Equal topical quality must give equal domain authority.

        The result must carry its language — that is how the ranking picks the
        right national source list.
        """
        ru = self.svc.calculate_index(
            {"url": "https://lenta.ru/x", "embedding_score": 0.5, "language": "ru"}
        )
        en = self.svc.calculate_index(
            {"url": "https://github.com/x", "embedding_score": 0.5, "language": "en"}
        )
        assert abs(ru - en) < 1e-9

    def test_language_is_required_for_national_domains(self):
        """Without a language only the language-neutral list applies."""
        assert self.svc._calculate_domain_authority("https://lenta.ru/x", None) < 1.0
        assert self.svc._calculate_domain_authority("https://lenta.ru/x", "ru") == 1.0


class TestDomainMatchingIsHostBased:
    def setup_method(self):
        self.svc = IndexingService()

    def test_lookalike_domain_is_not_trusted(self):
        """A substring check scored "notwikipedia.org" as trusted."""
        assert self.svc._calculate_domain_authority("https://notwikipedia.org/x") < 1.0
        assert self.svc._calculate_domain_authority("https://github.com.evil.net/x") < 1.0

    def test_bare_docs_prefix_is_not_a_domain(self):
        assert self.svc._calculate_domain_authority("https://example.com/docs/x") < 1.0

    def test_subdomain_of_trusted_domain_is_trusted(self):
        assert self.svc._calculate_domain_authority("https://news.github.com/x") == 1.0

    def test_url_without_scheme(self):
        assert self.svc._calculate_domain_authority("github.com/x", "en") == 1.0


class TestRelevanceIndexScale:
    def test_index_is_fraction_not_percentage(self):
        """calculate_index accumulates weights that sum to 1.0, so the result is
        a 0..1 fraction even though the docstring once claimed 0-100.

        The clamp is now `min(index, 1.0)` — against 100.0 it never fired and
        float rounding could push the value above 1.0.
        """
        svc = IndexingService()
        best = svc.calculate_index({
            "url": "https://github.com/x",
            "created_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "embedding_score": 1.0,
            "score": 1.0,
        }, custom_sites=["https://github.com/x"])
        assert best <= 1.0
        assert best > 0.9

    def test_index_never_exceeds_one(self):
        svc = IndexingService()
        result = {
            "url": "https://github.com/x",
            "created_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "embedding_score": 1.0,
            "score": 1.0,
        }
        assert svc.calculate_index(result, custom_sites=["https://github.com/x"]) <= 1.0

    def test_index_never_negative(self):
        svc = IndexingService()
        result = {"url": "https://a.com", "embedding_score": -1.0, "score": -1.0}
        assert svc.calculate_index(result) >= 0.0


class TestExaScoreComponent:
    def test_exa_score_contributes_to_index(self):
        """Exa's own relevance signal must influence the ranking."""
        svc = IndexingService()
        high = svc.calculate_index({"url": "https://a.com", "embedding_score": 0.5, "score": 0.99})
        low = svc.calculate_index({"url": "https://a.com", "embedding_score": 0.5, "score": 0.01})
        assert high > low

    def test_exa_score_weight_is_25_percent(self):
        svc = IndexingService()
        base = svc.calculate_index({"url": "https://a.com", "embedding_score": 0.0})
        with_score = svc.calculate_index({"url": "https://a.com", "embedding_score": 0.0, "score": 1.0})
        assert abs((with_score - base) - 0.25) < 1e-9

    def test_missing_exa_score_is_treated_as_zero(self):
        svc = IndexingService()
        without = svc.calculate_index({"url": "https://a.com", "embedding_score": 0.5})
        explicit_zero = svc.calculate_index({"url": "https://a.com", "embedding_score": 0.5, "score": 0.0})
        assert without == explicit_zero

    def test_weight_sum_is_100(self):
        svc = IndexingService()
        assert sum(svc.rules.model_dump().values()) == 100


class TestLanguageMatchComponent:
    def test_language_match_uses_result_value(self):
        svc = IndexingService()
        matched = svc.calculate_index({"url": "https://a.com", "language_match": 1.0})
        mismatched = svc.calculate_index({"url": "https://a.com", "language_match": 0.3})
        assert matched > mismatched

    def test_missing_language_match_defaults_to_full(self):
        svc = IndexingService()
        assert svc.calculate_index({"url": "https://a.com"}) == \
            svc.calculate_index({"url": "https://a.com", "language_match": 1.0})

    def test_language_match_weight_is_15_percent(self):
        svc = IndexingService()
        full = svc.calculate_index({"url": "https://a.com", "language_match": 1.0})
        zero = svc.calculate_index({"url": "https://a.com", "language_match": 0.0})
        assert abs((full - zero) - 0.15) < 1e-9


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
