import os
import logging
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
    DATABASE_PATH = _get_db_path()
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = _parse_port()
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    # Multilingual model: supports ru/de/it/en cross-lingual comparison.
    EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    # Lowered from 0.5: cross-lingual cosine scores are naturally lower and the
    # English-only threshold silently dropped every non-English result.
    RELEVANCE_THRESHOLD = 0.3
    OCR_ENABLED = True
    TESSERACT_PATH = os.getenv("TESSERACT_PATH", "tesseract")

    # Source language used when translating the user query.
    SOURCE_LANGUAGE = os.getenv("SOURCE_LANGUAGE", "ru")

    # Registry of supported languages. Each entry carries the UI label shown on
    # the frontend and the national domains used to bias Exa results toward that
    # language (Exa has no native `lang` param, so we lean on `includeDomains`).
    LANGUAGES = {
        "ru": {
            "label": "Русский",
            "include_domains": ["lenta.ru", "ria.ru", "habr.com", "vc.ru", "tass.ru"],
        },
        "en": {
            "label": "English",
            "include_domains": [],
        },
        "de": {
            "label": "Deutsch",
            "include_domains": ["de.wikipedia.org", "spiegel.de", "zeit.de", "heise.de"],
        },
        "it": {
            "label": "Italiano",
            "include_domains": ["it.wikipedia.org", "repubblica.it", "corriere.it"],
        },
    }

    # Languages selected by default on a fresh search. Russian first.
    DEFAULT_LANGUAGES = ["ru"]

    # Backwards-compatible flat list (order = display order).
    SUPPORTED_LANGUAGES = ["ru", "en", "de", "it"]

    @classmethod
    def language_domains(cls, lang: str) -> list:
        """Return national includeDomains for a language code (may be empty)."""
        entry = cls.LANGUAGES.get(lang) or {}
        return list(entry.get("include_domains", []))

    @classmethod
    def language_label(cls, lang: str) -> str:
        """Return the UI label for a language code."""
        entry = cls.LANGUAGES.get(lang) or {}
        return entry.get("label", lang)
