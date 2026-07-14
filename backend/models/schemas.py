from pydantic import BaseModel
from typing import List

class SearchQuery(BaseModel):
    query: str
    languages: List[str] = ["ru"]
    num_results: int = 10
    filter_by_relevance: bool = True
    search_custom_db: bool = True

class FilteringRules(BaseModel):
    relevance_score: float = 40
    domain_authority: float = 20
    content_freshness: float = 15
    language_match: float = 15
    custom_boost: float = 10
