import logging
import time
import uuid

import requests
from config import Config

logger = logging.getLogger(__name__)

# Map our internal language codes to the codes expected by the providers.
# Yandex and Google use the same ISO codes for these languages.
LANG_MAP = {"ru": "ru", "en": "en", "de": "de", "it": "it"}

# Browser-facing Yandex endpoint (the same one translate.yandex.com uses).
# No API key required. Gray area but far more stable than the Google "gtx"
# endpoint and the best quality for ru <-> de/it.
YANDEX_URL = "https://translate.yandex.net/api/v1/tr.json/translate"

# Unofficial Google endpoint, kept as a secondary fallback.
GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"

# Request timeout and retry policy. Both providers are unofficial endpoints
# that occasionally throttle, so a single failed request must not degrade the
# search into an untranslated query.
REQUEST_TIMEOUT = 8
MAX_ATTEMPTS = 3
RETRY_BACKOFF = 0.4


def _new_yandex_sid() -> str:
    """Yandex expects a `sid` (session id). A random UUID works fine."""
    return uuid.uuid4().hex


class Translator:
    def __init__(self):
        self._cache = {}
        self._source = Config.SOURCE_LANGUAGE
        self._sid = _new_yandex_sid()

    def translate(self, text: str, target_language: str) -> str:
        """Translate ``text`` into ``target_language``.

        Tries Yandex first, then the Google gtx endpoint, and finally returns
        the original text so search never breaks because of translation.
        Results are cached per (text, target) pair.
        """
        if not text:
            return text

        target = LANG_MAP.get(target_language)
        if not target:
            return text

        # No need to call a service when source == target.
        if target == self._source:
            return text

        cache_key = (text, target)
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._translate_yandex(text, target)
        if not result:
            result = self._translate_google(text, target)
        if not result:
            result = text

        self._cache[cache_key] = result
        return result

    @staticmethod
    def _get_with_retry(url: str, params: dict) -> requests.Response | None:
        """GET with a short retry/backoff for transient failures."""
        last_error = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                return requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            except requests.RequestException as e:
                last_error = e
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(RETRY_BACKOFF * (2 ** attempt))
        logger.warning("Request to %s failed after %d attempts: %s", url, MAX_ATTEMPTS, last_error)
        return None

    def _translate_yandex(self, text: str, target: str) -> str | None:
        resp = self._get_with_retry(
            YANDEX_URL,
            {
                "id": self._sid + "-0-0",
                "srv": "tr",
                "source": self._source,
                "lang": f"{self._source}-{target}",
                "text": text,
            },
        )
        if resp is None:
            return None
        try:
            if resp.status_code == 200:
                data = resp.json()
                # Response shape: {"lang": "...", "text": ["translated..."]}
                texts = data.get("text")
                if texts:
                    return "".join(texts)
        except Exception as e:
            logger.warning("Yandex Translate error: %s", e)
        return None

    def _translate_google(self, text: str, target: str) -> str | None:
        resp = self._get_with_retry(
            GOOGLE_URL,
            {"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text},
        )
        if resp is None:
            return None
        try:
            if resp.status_code == 200:
                parts = resp.json()[0]
                return "".join(p[0] for p in parts if p and p[0])
        except Exception as e:
            logger.warning("Google Translate error: %s", e)
        return None

    def translate_to_multiple(self, text: str, languages: list) -> dict:
        """Translate ``text`` into every language in ``languages``.

        The source language is preserved as ``"original"`` so callers always
        have the unmodified query available.
        """
        results = {"original": text}
        results[self._source] = text
        for lang in languages:
            if lang == self._source:
                continue
            results[lang] = self.translate(text, lang)
        return results
