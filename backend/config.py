import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def _get_db_path():
    path = os.getenv("DATABASE_PATH", "./database/myexa.db")
    if not os.path.isabs(path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, path.lstrip("./"))
    return os.path.normpath(path)


def _parse_port() -> int:
    raw = os.getenv("PORT", "3005")
    try:
        return int(raw)
    except (ValueError, TypeError):
        print(f"WARNING: Invalid PORT '{raw}', falling back to 3005")
        return 3005


class Config:
    EXA_API_KEY = os.getenv("EXA_API_KEY", "")

    # Base URL of the Exa API. Overridable so the backend can be pointed at a
    # mirror or a local stub — useful when api.exa.ai is unreachable from the
    # current network (Cloudflare blocks the whole host for some IP ranges).
    EXA_API_URL = os.getenv("EXA_API_URL", "https://api.exa.ai")

    # --- Fallback search provider (SearXNG) ---------------------------------
    # A local SearXNG instance aggregates several engines (Brave, Google CSE,
    # DuckDuckGo, ...) behind one JSON API and keeps the search working while
    # api.exa.ai is unreachable — Cloudflare answers 403 for whole IP ranges,
    # which is exactly what happened here.
    #
    # Exa stays the primary provider: the fallback is used only after the
    # primary has failed, so lifting the block needs no configuration change.
    SEARXNG_URL = os.getenv("SEARXNG_URL", "http://127.0.0.1:8080")
    SEARXNG_ENABLED = os.getenv("SEARXNG_ENABLED", "1").lower() not in ("0", "false", "no")
    SEARXNG_TIMEOUT = int(os.getenv("SEARXNG_TIMEOUT", "20"))

    DATABASE_PATH = _get_db_path()
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = _parse_port()
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    # Multilingual model: supports ru/de/it/en cross-lingual comparison.
    EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # --- Relevance filter ---------------------------------------------------
    # The filter scores a result by a weighted blend of the TITLE and a short
    # snippet. It deliberately does NOT embed the full ~4000-char highlights
    # blob: Exa builds highlights by selecting passages that match the query,
    # so that blob quotes the query almost verbatim and comparing it with the
    # query is close to tautological. Measured separation between relevant and
    # irrelevant results (relevant_mean - irrelevant_mean):
    #
    #   full highlights blob : ru +0.032  en +0.096  de -0.021  it -0.134
    #   title only           : ru +0.420  en +0.412  de +0.399  it +0.439
    #   blend 0.7/0.3        : ru +0.308  en +0.334  de +0.309  it +0.312
    #
    # See diagnostics/strategy_sweep.py and
    # diagnostics/measured_strategy_sweep.txt.
    RELEVANCE_THRESHOLD = 0.30
    # "blend" (default) | "title" | "chunk"
    RELEVANCE_STRATEGY = "blend"
    RELEVANCE_TITLE_WEIGHT = 0.7
    RELEVANCE_SNIPPET_WEIGHT = 0.3
    RELEVANCE_SNIPPET_CHARS = 600
    RELEVANCE_CHUNK_CHARS = 500
    # Per-language threshold overrides. Empty by default: the measured
    # separation is uniform across languages, so one global threshold is used.
    RELEVANCE_THRESHOLDS = {}

    OCR_ENABLED = True
    TESSERACT_PATH = os.getenv("TESSERACT_PATH", "tesseract")

    # Source language used when translating the user query.
    SOURCE_LANGUAGE = os.getenv("SOURCE_LANGUAGE", "ru")

    # Registry of supported languages. Each entry carries the UI label shown on
    # the frontend and the ISO 3166-1 country code used to localise Exa results.
    #
    # Exa has no native `lang` parameter. `includeDomains` would work, but it is
    # a HARD constraint ("results will only come from the matching domains"),
    # which confined the Russian corpus to five news/tech sites while English
    # searched the whole web. `userLocation` localises the ranking without
    # amputating the corpus, so the hard filter is empty by default and stays
    # available only as an explicit opt-in.
    LANGUAGES = {
        "ru": {
            "label": "Русский",
            "country": "RU",
            "include_domains": [],
        },
        "en": {
            "label": "English",
            "country": "US",
            "include_domains": [],
        },
        "de": {
            "label": "Deutsch",
            "country": "DE",
            "include_domains": [],
        },
        "it": {
            "label": "Italiano",
            "country": "IT",
            "include_domains": [],
        },
    }

    # Languages selected by default on a fresh search. Russian first.
    DEFAULT_LANGUAGES = ["ru"]

    # --- Domain authority ----------------------------------------------------
    # Language-neutral sources that are trusted in every language.
    GLOBAL_TRUSTED_DOMAINS = [
        "wikipedia.org",
        "github.com",
        "stackoverflow.com",
        "arxiv.org",
        "medium.com",
        "dev.to",
        "readthedocs.io",
        "developer.mozilla.org",
        "pubmed.ncbi.nlm.nih.gov",
        "nature.com",
    ]

    # National sources per language. Without these, a Russian result on
    # lenta.ru scored 0.7 while an English result on wikipedia.org scored 1.0,
    # which penalised every non-English domain in the ranking.
    LANGUAGE_TRUSTED_DOMAINS = {
        "ru": [
            "expert.ru", "kommersant.ru", "rbc.ru", "ria.ru", "tass.ru",
            "lenta.ru", "meduza.io", "nplus1.ru", "polit.ru", "vedomosti.ru",
            "interfax.ru", "iz.ru", "gazeta.ru", "the-village.ru", "vc.ru",
            "habr.com", "cian.ru", "dzen.ru", "mail.ru", "yandex.ru",
        ],
        "en": [
            "nytimes.com", "reuters.com", "bbc.com", "theguardian.com",
            "wired.com", "techcrunch.com", "sciencedirect.com", "springer.com",
            "ieee.org", "acm.org",
        ],
        "de": [
            "spiegel.de", "zeit.de", "heise.de", "golem.de", "chip.de",
            "faz.net", "welt.de", "sueddeutsche.de", "zeitpunkt.nrw",
            "cmu.de", "destatis.de",
        ],
        "it": [
            "repubblica.it", "corriere.it", "ilfattoquotidiano.it",
            "startpage.it", "treccani.it", "ilsole24ore.it", "lastampa.it",
            "ansa.it", "tg24.sky.it", "superando.it",
        ],
    }

    # Backwards-compatible flat list (order = display order).
    SUPPORTED_LANGUAGES = ["ru", "en", "de", "it"]

    @classmethod
    def language_domains(cls, lang: str) -> list:
        """Return national includeDomains for a language code (may be empty).

        Empty by default: a hard domain filter restricts Exa to those domains
        only. Use it only as an explicit, user-approved allowlist.
        """
        entry = cls.LANGUAGES.get(lang) or {}
        return list(entry.get("include_domains", []))

    @classmethod
    def language_country(cls, lang: str) -> str | None:
        """Return the ISO 3166-1 country code used to localise Exa results."""
        entry = cls.LANGUAGES.get(lang) or {}
        return entry.get("country") or None

    @classmethod
    def language_label(cls, lang: str) -> str:
        """Return the UI label for a language code."""
        entry = cls.LANGUAGES.get(lang) or {}
        return entry.get("label", lang)

    @classmethod
    def is_supported(cls, lang: str) -> bool:
        """Return True when ``lang`` is a registered language code."""
        return lang in cls.LANGUAGES

    @classmethod
    def language_threshold(cls, lang: str) -> float:
        """Return the relevance threshold for a language.

        Falls back to the global threshold unless a per-language override is
        configured in ``RELEVANCE_THRESHOLDS``.
        """
        override = cls.RELEVANCE_THRESHOLDS.get(lang)
        if override is not None:
            return float(override)
        return cls.RELEVANCE_THRESHOLD

    @classmethod
    def trusted_domains(cls, lang: str = None) -> list:
        """Return the trusted-domain list for a language.

        The language-neutral list is always included, so a Russian result on
        ``ru.wikipedia.org`` is trusted just like the English one.
        """
        domains = list(cls.GLOBAL_TRUSTED_DOMAINS)
        domains.extend(cls.LANGUAGE_TRUSTED_DOMAINS.get(lang, []))
        return domains
