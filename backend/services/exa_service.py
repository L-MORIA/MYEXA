import logging
import requests
from config import Config
from typing import List, Dict

logger = logging.getLogger(__name__)

EXA_API_URL = "https://api.exa.ai"


class ExaService:
    def __init__(self):
        self.api_key = Config.EXA_API_KEY
        if not self.api_key:
            logger.warning("EXA_API_KEY is empty — Exa search will fail")

    def _request(self, endpoint: str, data: dict) -> dict:
        resp = requests.post(
            f"{EXA_API_URL}{endpoint}",
            json=data,
            headers={"x-api-key": self.api_key},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error("Exa API error %s: %s", resp.status_code, resp.text[:300])
            return {}
        return resp.json()

    def search(self, query: str, num_results: int = 10, language: str = "en") -> List[Dict]:
        try:
            data = self._request("/search", {
                "query": query,
                "numResults": num_results,
                "type": "auto",
                "contents": {"highlights": {"maxCharacters": 4000}},
            })
            if not data:
                return []

            return [
                {
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "highlights": (item.get("highlights") or [""])[0],
                    "score": (item.get("highlightScores") or [0.0])[0],
                    "language": language,
                }
                for item in data.get("results") or []
            ]
        except Exception as e:
            logger.error("Exa search error: %s", e)
            return []

    def search_multiple_languages(
        self, query: str, languages: List[str], num_results: int = 10
    ) -> Dict[str, List[Dict]]:
        return {lang: self.search(query, num_results, lang) for lang in languages}

    def get_contents(self, urls: List[str]) -> List[Dict]:
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
        except Exception as e:
            logger.error("Exa get_contents error: %s", e)
            return []