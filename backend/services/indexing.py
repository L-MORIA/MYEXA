from datetime import UTC, datetime
from urllib.parse import urlparse

from config import Config
from models.schemas import FilteringRules


class IndexingService:
    def __init__(self):
        self.rules = FilteringRules()

    def calculate_index(self, result: dict, custom_sites: list[str] = None) -> float:
        """Calculate the relevance index as a fraction in the range 0..1.

        The index is the weighted sum of the components in ``FilteringRules``
        (whose weights sum to 100), so it is a 0..1 fraction — not a percentage.
        The frontend multiplies by 100 for display.
        """
        if custom_sites is None:
            custom_sites = []

        index = 0.0

        # Embedding similarity (cross-lingual) — 15%
        embedding_score = result.get("embedding_score", 0.0) or 0.0
        index += embedding_score * (self.rules.relevance_score / 100)

        # Exa's own relevance signal (highlightScores) — 25%
        # Previously parsed by the Exa service but ignored here, which threw
        # away the most trustworthy relevance signal available.
        exa_score = result.get("score", 0.0) or 0.0
        index += exa_score * (self.rules.exa_score / 100)

        # Domain authority (20%) — the language of the result decides which
        # national sources count as trusted.
        domain_authority = self._calculate_domain_authority(
            result.get("url", ""), result.get("language")
        )
        index += domain_authority * (self.rules.domain_authority / 100)

        # Content freshness (15%) — uses the publication date from Exa
        freshness_score = self._calculate_freshness(
            result.get("published_date") or result.get("created_at")
        )
        index += freshness_score * (self.rules.content_freshness / 100)

        # Language match (15%) — 1.0 when the document language matches the
        # requested one. The API layer sets this per result.
        language_score = result.get("language_match")
        if language_score is None:
            language_score = 1.0
        index += language_score * (self.rules.language_match / 100)

        # Custom boost (10%)
        custom_boost = 1.0 if result.get("url") in custom_sites else 0.0
        index += custom_boost * (self.rules.custom_boost / 100)

        return min(max(index, 0.0), 1.0)

    def _calculate_domain_authority(self, url: str, language: str = None) -> float:
        """Estimate domain authority (0-1).

        Matching is done on the hostname, not on a substring of the whole URL:
        a substring check scored "notwikipedia.org" as trusted and treated the
        "docs." prefix as a domain.
        """
        host = ""
        try:
            # A URL without a scheme ("github.com/x") is parsed as a path, so
            # the scheme is added before extracting the host.
            candidate = url if "//" in url else "//" + url
            host = urlparse(candidate).hostname or ""
        except ValueError:
            host = ""

        host = host.lower()
        for domain in Config.trusted_domains(language):
            domain = domain.lower()
            if host == domain or host.endswith("." + domain):
                return 1.0

        # Check for HTTPS
        if url.startswith("https://"):
            return 0.7

        return 0.5

    def _calculate_freshness(self, created_at: str = None) -> float:
        """Calculate content freshness score (0-1)"""
        if not created_at:
            return 0.5

        try:
            created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            if created_date.tzinfo is None:
                created_date = created_date.replace(tzinfo=UTC)
            days_old = (datetime.now(UTC) - created_date).days

            # Newer is better
            if days_old <= 7:
                return 1.0
            elif days_old <= 30:
                return 0.8
            elif days_old <= 90:
                return 0.6
            elif days_old <= 365:
                return 0.4
            else:
                return 0.2
        except (ValueError, TypeError, AttributeError):
            return 0.5

    def rank_results(self, results: list[dict], custom_sites: list[str] = None) -> list[dict]:
        """Rank results by calculated index"""
        if custom_sites is None:
            custom_sites = []

        for result in results:
            result["relevance_index"] = self.calculate_index(result, custom_sites)

        # Sort by relevance index
        results.sort(key=lambda x: x["relevance_index"], reverse=True)
        return results
