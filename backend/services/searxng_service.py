import logging
import time
from datetime import UTC, datetime

import requests
from config import Config
from services.search_provider import ProviderError, SearchProvider

logger = logging.getLogger(__name__)

# SearXNG addresses the search language with a locale code. The two-letter
# codes used by MYEXA are not understood by every engine, so the locale is
# passed explicitly.
SEARXNG_LANGUAGES = {
    "ru": "ru-RU",
    "en": "en-US",
    "de": "de-DE",
    "it": "it-IT",
}

# Date formats seen in SearXNG results. Brave reports "20.04.2024 0:00:00",
# other engines report ISO-8601 or nothing at all.
_DATE_FORMATS = (
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)


class SearxngError(ProviderError):
    """Raised when the SearXNG instance is unreachable or answers with an error."""


class SearxngService(SearchProvider):
    """Fallback search provider backed by a local SearXNG instance.

    SearXNG aggregates several engines (Brave, Google CSE, DuckDuckGo, ...)
    behind one JSON API. It is used when the primary provider fails — for
    example while ``api.exa.ai`` is blocked by Cloudflare for this network.
    """

    name = "searxng"

    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = (base_url if base_url is not None else Config.SEARXNG_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else Config.SEARXNG_TIMEOUT
        # query + language -> (timestamp, results)
        self._cache: dict[tuple, tuple[float, list[dict]]] = {}

    def is_configured(self) -> bool:
        """Return True when the fallback may be used.

        The URL alone is not enough: the instance may simply not be running,
        and a disabled fallback must not be attempted at all.
        """
        return bool(Config.SEARXNG_ENABLED and self.base_url)

    def search(self, query: str, num_results: int = 10, language: str = "en",
               country: str = None) -> list[dict]:
        """Search SearXNG and return results in the MYEXA result format."""
        if not self.is_configured():
            raise SearxngError("SearXNG fallback is disabled")

        cache_key = (query, language, num_results)
        cached = self._cache.get(cache_key)
        if cached is not None:
            age = time.monotonic() - cached[0]
            if age < Config.SEARXNG_CACHE_TTL:
                # A copy: the caller annotates and scores the items in place.
                return [dict(item) for item in cached[1]]
            del self._cache[cache_key]

        params = {
            "q": query,
            "format": "json",
            "categories": "general",
            "safesearch": "0",
            "language": SEARXNG_LANGUAGES.get(language, language),
        }

        try:
            resp = requests.get(f"{self.base_url}/search", params=params, timeout=self.timeout)
        except Exception as e:
            raise SearxngError(f"SearXNG request failed: {e}") from e

        if resp.status_code != 200:
            logger.error("SearXNG API error %s: %s", resp.status_code, resp.text[:200])
            raise SearxngError(f"SearXNG API error {resp.status_code}")

        try:
            data = resp.json()
        except ValueError as e:
            raise SearxngError("SearXNG returned a malformed JSON body") from e

        raw_results = data.get("results") or []
        parsed = [self._parse_result(item, language) for item in raw_results[:num_results]]
        self._normalize_scores(parsed)

        # An empty answer is not the same thing as "nothing found": when every
        # engine failed — a rate limit from the upstream engines, for example
        # — the instance answers with an empty list and a list of failures.
        # Reporting that as "no results" would hide a broken backend.
        failures = self._parse_failures(data.get("unresponsive_engines"))
        if not parsed and failures:
            reasons = "; ".join(f"{name}: {reason}" for name, reason in failures)
            raise SearxngError(f"no search engine answered ({reasons})")

        self._remember(cache_key, parsed)
        return parsed

    def _remember(self, cache_key: tuple, results: list[dict]) -> None:
        """Store a result set, keeping the cache bounded."""
        if Config.SEARXNG_CACHE_TTL <= 0:
            return
        self._cache[cache_key] = (time.monotonic(), [dict(item) for item in results])
        while len(self._cache) > max(1, Config.SEARXNG_CACHE_SIZE):
            oldest = next(iter(self._cache))
            del self._cache[oldest]

    @staticmethod
    def _parse_failures(raw) -> list[tuple[str, str]]:
        """Normalise the ``unresponsive_engines`` field of the SearXNG answer.

        The field comes in several shapes depending on the SearXNG version:
        a list of ``[name, reason]`` pairs, a list of dicts, or a flat pair.
        """
        failures: list[tuple[str, str]] = []
        if not raw:
            return failures

        if isinstance(raw, dict):
            raw = [raw]
        elif (isinstance(raw, list) and len(raw) == 2
                and all(isinstance(part, str) for part in raw)):
            raw = [raw]

        for entry in raw or []:
            if isinstance(entry, dict):
                name = entry.get("engine") or entry.get("name") or "?"
                reason = entry.get("error_type") or entry.get("reason") or "unknown error"
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                name, reason = str(entry[0]), str(entry[1])
            else:
                name, reason = "?", str(entry)
            failures.append((name, reason))
        return failures

    @staticmethod
    def _parse_result(item: dict, language: str) -> dict:
        """Normalise one SearXNG result into the MYEXA result format.

        The field names match the Exa adapter, so the rest of the pipeline
        (embedding filter, language detection, ranking) needs no changes.
        """
        content = (item.get("content") or "").strip()
        return {
            "url": item.get("url", ""),
            "title": (item.get("title") or "").strip(),
            "highlights": content,
            "highlight_scores": [],
            "score": 0.0,
            "published_date": SearxngService._parse_date(item.get("publishedDate")),
            "language": language,
            "engine": item.get("engine", ""),
            "provider": "searxng",
        }

    @staticmethod
    def _parse_date(value: str) -> str | None:
        """Convert a SearXNG date string into an ISO-8601 timestamp.

        The freshness score parses ISO-8601 only, so a date in a local format
        ("20.04.2024 0:00:00") would silently fall back to the neutral 0.5
        and make every result look equally stale.
        """
        if not value:
            return None
        value = value.strip()
        for fmt in _DATE_FORMATS:
            try:
                parsed = datetime.strptime(value, fmt)
            except ValueError:
                continue
            return parsed.replace(tzinfo=UTC).isoformat()
        return None

    @staticmethod
    def _normalize_scores(results: list[dict]) -> None:
        """Bring the per-engine scores onto a common 0..1 scale.

        SearXNG reports an engine-specific score: Brave counts down from 3,
        Google CSE returns values around 0.4. Feeding those numbers into the
        ranking directly would let one engine dominate the whole index, and a
        score of 3 would saturate it. Every engine's own results are therefore
        scaled linearly to 0..1 — each engine contributes its best result at
        1.0 and its worst at 0.0 — and the order of the merged list is kept.
        """
        by_engine: dict[str, list[dict]] = {}
        for result in results:
            by_engine.setdefault(result.get("engine") or "", []).append(result)

        for group in by_engine.values():
            count = len(group)
            for position, item in enumerate(group):
                item["score"] = 1.0 if count == 1 else 1.0 - (position / (count - 1))
