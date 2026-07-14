import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

LANG_MAP = {"en": "en", "de": "de", "it": "it"}
GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"


class Translator:
    def __init__(self):
        self._cache = {}

    def translate(self, text: str, target_language: str) -> str:
        target = LANG_MAP.get(target_language)
        if not target:
            return text

        cache_key = (text, target)
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._translate_google(text, target)
        if not result:
            result = self._translate_libretranslate(text, target)
        if not result:
            result = text

        self._cache[cache_key] = result
        return result

    def _translate_google(self, text: str, target: str) -> str | None:
        import requests

        try:
            resp = requests.get(
                GOOGLE_URL,
                params={"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text},
                timeout=5,
            )
            if resp.status_code == 200:
                parts = resp.json()[0]
                return "".join(p[0] for p in parts if p[0])
        except Exception as e:
            logger.warning("Google Translate error: %s", e)
        return None

    def _translate_libretranslate(self, text: str, target: str) -> str | None:
        import requests

        try:
            resp = requests.post(
                "https://libretranslate.de/translate",
                json={"q": text, "source": "auto", "target": target},
                timeout=5,
            )
            if resp.status_code == 200:
                return resp.json().get("translatedText")
        except Exception as e:
            logger.warning("LibreTranslate error: %s", e)
        return None

    def translate_to_multiple(self, text: str, languages: list) -> dict:
        results = {"original": text}
        for lang in languages:
            results[lang] = self.translate(text, lang)
        return results