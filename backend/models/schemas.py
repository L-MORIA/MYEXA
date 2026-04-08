from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class SearchQuery(BaseModel):
    query: str
    languages: List[str] = ["en", "de", "it"]
    num_results: int = 10
    filter_by_relevance: bool = True
    search_custom_db: bool = True

class SearchResult(BaseModel):
    id: int
    query: str
    url: str
    title: str
    content: Optional[str]
    relevance_score: float
    language: str
    source: str
    created_at: datetime

class CustomSite(BaseModel):
    url: str
    title: str
    category: Optional[str] = None
    tags: Optional[str] = None

class FilteringRules(BaseModel):
    relevance_score: float = 40
    domain_authority: float = 20
    content_freshness: float = 15
    language_match: float = 15
    custom_boost: float = 10

class OCRRequest(BaseModel):
    file_path: str
    language: str = "en"

class OCRResult(BaseModel):
    text: str
    confidence: float
    language: str
