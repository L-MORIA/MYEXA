"""Language detection for search results.

The ranking used to assume every result was already in the requested language
(`language_score = 1.0` with the comment "Assume language already matched"),
which was only "true" as long as a hard domain filter pinned each language to
a handful of sites. Once that filter is gone the language of a result has to
be detected for real.

The detector is restricted to the languages MYEXA supports. The unrestricted
detector mislabels short English titles as French, and the low-accuracy mode
mislabels "artificial intelligence in medicine" as Italian — both are silent
quality bugs, so neither is used.
"""

import logging

logger = logging.getLogger(__name__)

# ISO 639-1 codes MYEXA supports.
SUPPORTED_CODES = ("ru", "en", "de", "it")

# lingua language enum -> our code
_LINGUA_CODES = {
    "RUSSIAN": "ru",
    "ENGLISH": "en",
    "GERMAN": "de",
    "ITALIAN": "it",
}


class LanguageDetector:
    """Detects the language of a result and scores how well it matches."""

    def __init__(self):
        self._detector = None
        self._available = False
        self._build()

    def _build(self):
        try:
            from lingua import Language, LanguageDetectorBuilder

            languages = [
                getattr(Language, name)
                for name in ("RUSSIAN", "ENGLISH", "GERMAN", "ITALIAN")
                if hasattr(Language, name)
            ]
            builder = LanguageDetectorBuilder.from_languages(*languages)
            self._detector = builder.build()
            self._available = True
            logger.info("Language detector ready (%d languages)", len(languages))
        except Exception as e:
            logger.warning("Language detector unavailable: %s", e)
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def detect(self, text: str) -> str | None:
        """Return the ISO code of ``text`` or None when it cannot be decided."""
        if not self._available or not text or not text.strip():
            return None
        try:
            detected = self._detector.detect_language_of(text)
        except Exception as e:
            logger.warning("Language detection failed: %s", e)
            return None
        if detected is None:
            return None
        return _LINGUA_CODES.get(detected.name)

    def match(self, text: str, target: str) -> float:
        """Score how well ``text`` matches the requested language.

        * 1.0 — detected language equals the requested one
        * 0.3 — detected as a different supported language
        * 0.5 — language could not be determined
        """
        detected = self.detect(text)
        if detected is None:
            return 0.5
        return 1.0 if detected == target else 0.3

    def annotate(self, results: list[dict], target: str,
                 sample_chars: int = 400) -> list[dict]:
        """Attach ``detected_language`` and ``language_match`` to each result."""
        for item in results:
            title = item.get("title") or ""
            highlights = item.get("highlights") or ""
            text = f"{title}. {highlights[:sample_chars]}".strip()
            item["detected_language"] = self.detect(text)
            item["language_match"] = self.match(text, target)
        return results

    def filter_by_language(self, results: list[dict]) -> list[dict]:
        """Keep only results whose detected language matches the request.

        Strict on purpose. The previous keep-all rule (mixed results were
        shown with a warning when fewer than half matched) read as broken:
        a German tab full of English pages is not a German tab, whatever the
        banner says. The caller reports how many results were dropped and
        which languages they were in, so an empty tab is explained instead
        of mysterious.
        """
        for item in results:
            item["language_mismatch"] = item.get("language_match", 1.0) < 1.0
        return [item for item in results if not item["language_mismatch"]]
