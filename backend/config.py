import os
import logging
from dotenv import load_dotenv

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_BACKEND_DIR, ".."))

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


def _resolve_database_path() -> str:
    raw = os.getenv("DATABASE_PATH", os.path.join("database", "myexa.db"))
    if os.path.isabs(raw):
        return os.path.normpath(raw)
    return os.path.normpath(os.path.join(_PROJECT_ROOT, raw))


class Config:
    # API
    EXA_API_KEY = os.getenv("EXA_API_KEY", "")
    
    # Database (always relative to project root unless DATABASE_PATH is absolute)
    DATABASE_PATH = _resolve_database_path()
    
    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "3005"))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Embedding
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Filtering thresholds
    RELEVANCE_THRESHOLD = 0.5
    
    # Languages
    SUPPORTED_LANGUAGES = ["en", "de", "it"]
    
    # OCR
    OCR_ENABLED = True
    TESSERACT_PATH = os.getenv("TESSERACT_PATH", "tesseract")
    
    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3005,http://127.0.0.1:3005").split(",")


def validate_config():
    """Validate critical configuration values (warn only; server can still start)."""
    logger = logging.getLogger(__name__)
    if not Config.EXA_API_KEY or Config.EXA_API_KEY == "your_api_key_here":
        logger.warning(
            "EXA_API_KEY is not set or is still placeholder. "
            "EXA search may fail until you set a valid key in .env."
        )


def setup_logging():
    """Configure structured logging"""
    log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    return logging.getLogger(__name__)
