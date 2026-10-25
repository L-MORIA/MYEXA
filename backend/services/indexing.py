from datetime import datetime
from typing import List, Dict
from urllib.parse import urlparse
from models.schemas import FilteringRules

# Domains that count as "trusted" for the domain-authority component. Matched
# against the URL hostname only (exact or subdomain), never against the path
# or a look-alike host such as github.com.evil.example.
TRUSTED_DOMAINS = [
    "github.com", "stackoverflow.com", "wikipedia.org",
    "arxiv.org", "medium.com", "dev.to",
]


class IndexingService:
    def __init__(self):
        self.rules = FilteringRules()

    def calculate_index(self, result: Dict, custom_sites: List[str] = None) -> float:
        """Calculate relevance index (0-100) based on filtering rules.

        Each component is normalized to 0-1 and multiplied by its weight
        (weights in FilteringRules sum to 100).
        """
        if custom_sites is None:
            custom_sites = []

        index = 0.0

        # Relevance score (40%)
        embedding_score = result.get("embedding_score", 0.0)
        index += embedding_score * self.rules.relevance_score

        # Domain authority (20%)
        domain_authority = self._calculate_domain_authority(result.get("url", ""))
        index += domain_authority * self.rules.domain_authority

        # Content freshness (15%)
        freshness_score = self._calculate_freshness(result.get("created_at"))
        index += freshness_score * self.rules.content_freshness

        # Language match (15%)
        language_score = 1.0  # Assume language already matched
        index += language_score * self.rules.language_match

        # Custom boost (10%)
        custom_boost = 1.0 if result.get("url") in custom_sites else 0.0
        index += custom_boost * self.rules.custom_boost

        return min(index, 100.0)

    def _calculate_domain_authority(self, url: str) -> float:
        """Estimate domain authority (0-1) from the URL hostname."""
        if not url:
            return 0.5

        try:
            parsed = urlparse(url if "//" in url else f"https://{url}")
            host = (parsed.hostname or "").lower()
        except ValueError:
            return 0.5

        if not host:
            return 0.5

        if host.startswith("docs."):
            return 1.0

        for domain in TRUSTED_DOMAINS:
            if host == domain or host.endswith(f".{domain}"):
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
            days_old = (datetime.now(created_date.tzinfo) - created_date).days

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
    
    def rank_results(self, results: List[Dict], custom_sites: List[str] = None) -> List[Dict]:
        """Rank results by calculated index"""
        if custom_sites is None:
            custom_sites = []
        
        for result in results:
            result["relevance_index"] = self.calculate_index(result, custom_sites)
        
        # Sort by relevance index
        results.sort(key=lambda x: x["relevance_index"], reverse=True)
        return results
