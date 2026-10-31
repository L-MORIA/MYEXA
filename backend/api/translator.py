import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from config import Config

logger = logging.getLogger(__name__)

# Map our internal language codes to the codes expected by the providers.
# Google and MyMemory use the same ISO codes for these languages.
LANG_MAP = {"ru": "ru", "en": "en", "de": "de", "it": "it"}

# Unofficial Google endpoint. It works without a key but throttles by IP
# (HTTP 429) once the searches come in bursts, so it cannot be the only
# provider.
GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"

# MyMemory: free, keyless translation API. The anonymous quota is per IP and
# per day, which is ample for search queries — and the cache below keeps
# repeated queries from spending it at all.
MYMEMORY_URL = "https://api.mymemory.translated.net/get"

# Optional Yandex Translate API v1.5 key. The old keyless v1 endpoint was
# switched off server-side (HTTP 410 "no longer active"), so Yandex is only
# used when the user configured a real key in .env.
YANDEX_V15_URL = "https://translate.yandex.net/api/v1.5/tr.json/translate"
YANDEX_API_KEY = os.getenv("YANDEX_TRANSLATE_API_KEY", "")

# The translation cache is capped: on a long-running server an unbounded
# dict grows until the process runs out of memory.
MAX_CACHE_ENTRIES = 1024

# Request timeout and retry policy. The providers are unofficial or free
# endpoints that occasionally throttle, so a single failed request must not
# degrade the search into an untranslated query.
REQUEST_TIMEOUT = 8
MAX_ATTEMPTS = 3
RETRY_BACKOFF = 0.4


class Translator:
    def __init__(self):
        self._cache = {}
        self._source = Config.SOURCE_LANGUAGE

    def translate(self, text: str, target_language: str) -> str:
        """Translate ``text`` into ``target_language``.

        Tries Yandex v1.5 (when a key is configured), then the Google gtx
        endpoint, then MyMemory. When every provider fails the original text
        comes back — search must not break because of translation — but the
        failure is logged and reported to the caller through
        ``translate_to_multiple``, so the interface can say that the results
        were found in the wrong language.
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
            # A hit refreshes the recency: the least recently used entry is
            # the one that is dropped.
            self._cache[cache_key] = self._cache.pop(cache_key)
            return self._cache[cache_key]

        result = None
        if YANDEX_API_KEY:
            result = self._translate_yandex_v15(text, target)
        if not result:
            result = self._translate_google(text, target)
        if not result:
            result = self._translate_mymemory(text, target)

        if result:
            # Only successful translations are cached: a cached failure would
            # pin the untranslated query for the whole process lifetime even
            # after the provider recovers.
            self._cache[cache_key] = result
            self._trim_cache()
            return result

        logger.warning(
            "Translation to '%s' failed on every provider — the query will be "
            "searched untranslated: %r", target, text,
        )
        return text

    def _trim_cache(self) -> None:
        """Drop the least recently used entries when the cache grows too large."""
        while len(self._cache) > MAX_CACHE_ENTRIES:
            oldest = next(iter(self._cache))
            del self._cache[oldest]

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

    def _translate_yandex_v15(self, text: str, target: str) -> str | None:
        """Yandex Translate API v1.5 — requires a key, best ru <-> de/it quality."""
        resp = self._get_with_retry(
            YANDEX_V15_URL,
            {
                "key": YANDEX_API_KEY,
                "lang": f"{self._source}-{target}",
                "text": text,
            },
        )
        if resp is None:
            return None
        try:
            if resp.status_code == 200:
                texts = resp.json().get("text")
                if texts:
                    return "".join(texts)
            else:
                logger.warning("Yandex v1.5 answered %s: %s", resp.status_code, resp.text[:120])
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

    def _translate_mymemory(self, text: str, target: str) -> str | None:
        resp = self._get_with_retry(
            MYMEMORY_URL,
            {"q": text, "langpair": f"{self._source}|{target}"},
        )
        if resp is None:
            return None
        try:
            if resp.status_code == 200:
                translated = resp.json().get("responseData", {}).get("translatedText")
                # MyMemory sometimes pads the translation with a stray
                # separator ("Artificial Intelligence/").
                if translated:
                    return translated.strip().strip("/").strip() or None
        except Exception as e:
            logger.warning("MyMemory Translate error: %s", e)
        return None

    def translate_to_multiple(self, text: str, languages: list) -> dict:
        """Translate ``text`` into every language in ``languages``.

        The source language is preserved as ``"original"`` so callers always
        have the unmodified query available. Languages whose translation
        failed on every provider are listed under ``"_failed_languages"`` so
        the interface can warn that those tabs were searched untranslated.

        The languages are translated in parallel: the calls are independent
        network round-trips, and doing them one after another added the
        provider's latency to every one of them.
        """
        results = {"original": text}
        results[self._source] = text

        targets = [lang for lang in languages if lang != self._source]
        if not targets:
            return results

        if len(targets) == 1:
            results[targets[0]] = self.translate(text, targets[0])
        else:
            with ThreadPoolExecutor(max_workers=len(targets)) as pool:
                futures = {
                    lang: pool.submit(self.translate, text, lang)
                    for lang in targets
                }
                for lang, future in futures.items():
                    results[lang] = future.result()

        # A "translation" that equals the input on a language the providers
        # were supposed to translate into is a failure — the cache holds the
        # previous successful result in that case, so this only fires when
        # every provider came back empty.
        failed = [
            lang for lang in targets
            if not results.get(lang) or results[lang] == text
        ]
        if failed:
            results["_failed_languages"] = failed
        return results
