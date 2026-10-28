import logging

import requests
from config import Config
from services.search_provider import ProviderError, SearchProvider

logger = logging.getLogger(__name__)

EXA_API_URL = "https://api.exa.ai"


class ExaError(ProviderError):
    """Raised when the Exa API is unreachable or answers with an error.

    Previously every transport or HTTP failure was swallowed and turned into
    an empty result list, so an API outage looked exactly like "no results
    found" to the user.
    """

    def __init__(self, message: str, status_code: int = None, body: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class ExaService(SearchProvider):
    name = "exa"

    def __init__(self):
        self.api_key = Config.EXA_API_KEY
        if not self.api_key:
            logger.warning("EXA_API_KEY is empty — Exa search will fail")

    def _request(self, endpoint: str, data: dict) -> dict:
        """Send a request to Exa and return the decoded body.

        Raises ``ExaError`` on transport failures, on a non-200 answer and on
        a malformed body.
        """
        try:
            resp = requests.post(
                f"{Config.EXA_API_URL}{endpoint}",
                json=data,
                headers={"x-api-key": self.api_key},
                timeout=15,
            )
        except Exception as e:
            raise ExaError(f"Exa request failed: {e}") from e

        if resp.status_code != 200:
            logger.error("Exa API error %s: %s", resp.status_code, resp.text[:300])
            raise ExaError(
                f"Exa API error {resp.status_code}",
                status_code=resp.status_code,
                body=resp.text[:300],
            )

        try:
            return resp.json()
        except ValueError as e:
            raise ExaError("Exa returned a malformed JSON body") from e

    def search(self, query: str, num_results: int = 10, language: str = "en",
               include_domains: list[str] = None,
               country: str = None) -> list[dict]:
        """Search Exa for ``query``.

        Exa has no native `lang` parameter. Two mechanisms are used instead:

        * ``country`` -> ``userLocation`` (ISO 3166-1 code) localises the
          ranking toward a country without restricting the corpus.
        * ``include_domains`` -> ``includeDomains`` is a HARD filter and is only
          sent when explicitly requested.
        """
        try:
            payload = {
                "query": query,
                "numResults": num_results,
                "type": "auto",
                "contents": {"highlights": {"maxCharacters": 4000}},
            }
            if country:
                payload["userLocation"] = country
            if include_domains:
                payload["includeDomains"] = list(include_domains)

            data = self._request("/search", payload)
            if not data:
                return []

            return [self._parse_result(item, language) for item in data.get("results") or []]
        except ExaError:
            raise
        except Exception as e:
            logger.error("Exa search error: %s", e)
            raise ExaError(f"Exa search failed: {e}") from e

    @staticmethod
    def _parse_result(item: dict, language: str) -> dict:
        """Normalise one Exa search result.

        ``publishedDate`` is preserved so freshness scoring has real data, and
        every ``highlightScores`` entry is kept (not just the first) because
        the first highlight is not necessarily the most relevant one.
        """
        highlights = item.get("highlights") or []
        highlight_scores = item.get("highlightScores") or []
        return {
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "highlights": highlights[0] if highlights else "",
            "highlight_scores": list(highlight_scores),
            "score": highlight_scores[0] if highlight_scores else 0.0,
            "published_date": item.get("publishedDate"),
            "language": language,
        }

    def search_multiple_languages(
        self, query: str, languages: list[str], num_results: int = 10
    ) -> dict[str, list[dict]]:
        return {lang: self.search(query, num_results, lang) for lang in languages}

    def get_contents(self, urls: list[str]) -> list[dict]:
        try:
            data = self._request("/contents", {
                "ids": urls,
                "text": {"maxCharacters": 20000},
            })
            if not data:
                return []

            return [
                {
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "text": item.get("text", ""),
                }
                for item in data.get("results") or []
            ]
        except ExaError:
            raise
        except Exception as e:
            logger.error("Exa get_contents error: %s", e)
            raise ExaError(f"Exa get_contents failed: {e}") from e
