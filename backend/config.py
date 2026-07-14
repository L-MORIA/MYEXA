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
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    RELEVANCE_THRESHOLD = 0.5
    SUPPORTED_LANGUAGES = ["en", "de", "it"]
    OCR_ENABLED = True
    TESSERACT_PATH = os.getenv("TESSERACT_PATH", "tesseract")
