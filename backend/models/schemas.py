from pydantic import BaseModel, Field, field_validator
from typing import List

from config import Config

class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1)
    languages: List[str] = ["ru"]
    num_results: int = Field(10, ge=1, le=50)
    filter_by_relevance: bool = True
    search_custom_db: bool = True

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank")
        return v

    @field_validator("languages")
    @classmethod
    def languages_supported(cls, v: List[str]) -> List[str]:
        unknown = [lang for lang in v if lang not in Config.SUPPORTED_LANGUAGES]
        if unknown:
            supported = ", ".join(Config.SUPPORTED_LANGUAGES)
            raise ValueError(
                f"unsupported language(s): {', '.join(unknown)}. "
                f"Supported languages: {supported}"
            )
        return v

class FilteringRules(BaseModel):
    relevance_score: float = 40
    domain_authority: float = 20
    content_freshness: float = 15
    language_match: float = 15
    custom_boost: float = 10
