
from pydantic import BaseModel, Field, field_validator


class SearchQuery(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    languages: list[str] = Field(default_factory=lambda: ["ru"], max_length=8)
    num_results: int = Field(default=10, ge=1, le=100)
    filter_by_relevance: bool = True
    search_custom_db: bool = True
    # Optional override of the relevance threshold (0..1). When omitted the
    # per-language default from Config is used.
    relevance_threshold: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("query")
    @classmethod
    def _query_must_not_be_blank(cls, value: str) -> str:
        # A query of spaces passes min_length but is useless: it reaches the
        # search engine and costs a request.
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class FilteringRules(BaseModel):
    """Weights of the relevance index. The sum must stay at 100."""

    relevance_score: float = 15      # embedding similarity (cross-lingual)
    exa_score: float = 25            # Exa's own highlightScores
    domain_authority: float = 20
    content_freshness: float = 15
    language_match: float = 15
    custom_boost: float = 10
