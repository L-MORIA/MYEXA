import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API
    EXA_API_KEY = os.getenv("EXA_API_KEY", "")
    
    # Database
    DATABASE_PATH = os.getenv("DATABASE_PATH", "./database/myexa.db")
    
    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 3005))
    
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
