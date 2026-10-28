import logging

import torch
from config import Config
from sentence_transformers import SentenceTransformer, util

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Cross-lingual relevance filter.

    The scoring strategy matters more than the threshold. Exa builds
    ``highlights`` by picking passages that match the query, so a full
    highlights blob quotes the query back and scoring it against the query is
    nearly tautological — measured separation between relevant and irrelevant
    results was only +0.03 in Russian and *negative* in German and Italian.

    The title states what the page is about, so it carries the topical signal.
    A short snippet is blended in at a lower weight to recover results whose
    title is uninformative. See diagnostics/strategy_sweep.py.
    """

    def __init__(self):
        try:
            self.model = SentenceTransformer(Config.EMBEDDING_MODEL)
            self.model.eval()
            self._available = True
        except Exception as e:
            logger.error("Failed to load embedding model: %s", e)
            self._available = False

    @torch.no_grad()
    def _get_embedding(self, text: str):
        return self.model.encode(text, convert_to_tensor=True)

    def calculate_similarity(self, query_embedding, text_embedding) -> float:
        sim = util.pytorch_cos_sim(query_embedding, text_embedding)
        return float(sim[0][0])

    # ── Scoring strategies ──────────────────────────────────────────────────

    def _title_text(self, item: dict) -> str:
        return (item.get("title") or "").strip()

    def _snippet_text(self, item: dict) -> str:
        highlights = item.get("highlights") or ""
        return highlights[:Config.RELEVANCE_SNIPPET_CHARS].strip()

    def _score_title(self, query_embedding, item: dict) -> float:
        return self.calculate_similarity(query_embedding, self._get_embedding(self._title_text(item)))

    def _score_blend(self, query_embedding, item: dict) -> float:
        """Weighted blend of the title and a short snippet."""
        title = self._title_text(item)
        snippet = self._snippet_text(item)
        if not title:
            return self.calculate_similarity(query_embedding, self._get_embedding(snippet))
        if not snippet:
            return self._score_title(query_embedding, item)

        title_sim = self.calculate_similarity(query_embedding, self._get_embedding(title))
        snippet_sim = self.calculate_similarity(query_embedding, self._get_embedding(snippet))
        return (
            title_sim * Config.RELEVANCE_TITLE_WEIGHT
            + snippet_sim * Config.RELEVANCE_SNIPPET_WEIGHT
        )

    def _score_chunk(self, query_embedding, item: dict) -> float:
        """Max similarity over the title and fixed-size chunks of the body."""
        best = self._score_title(query_embedding, item)
        blob = item.get("highlights") or ""
        size = Config.RELEVANCE_CHUNK_CHARS
        for start in range(0, len(blob), size):
            chunk = blob[start:start + size]
            if len(chunk) < 80:
                continue
            sim = self.calculate_similarity(query_embedding, self._get_embedding(chunk))
            best = max(best, sim)
        return best

    def score_item(self, query_embedding, item: dict, strategy: str = None) -> float:
        """Score one result against the query embedding."""
        strategy = strategy or Config.RELEVANCE_STRATEGY
        if strategy == "title":
            return self._score_title(query_embedding, item)
        if strategy == "chunk":
            return self._score_chunk(query_embedding, item)
        return self._score_blend(query_embedding, item)

    # ── Filtering ───────────────────────────────────────────────────────────

    def filter_results(self, query: str, items: list[dict],
                      threshold: float = None,
                      strategy: str = None) -> list[dict]:
        """Keep only results whose relevance score reaches ``threshold``.

        When the model is unavailable the input is returned unchanged — a
        missing model must not silently empty the result set.

        When *nothing* passes the threshold an empty list is returned. The
        previous behaviour returned every item with a zero score, which masked
        "nothing was relevant" as "everything is relevant".
        """
        if not self._available:
            return items

        if threshold is None:
            threshold = Config.RELEVANCE_THRESHOLD

        try:
            query_embedding = self._get_embedding(query)
        except Exception as e:
            logger.error("Embedding query failed: %s", e)
            self._available = False
            return items

        filtered = []
        for item in items:
            text = self._title_text(item) or self._snippet_text(item)
            if not text:
                continue

            try:
                similarity = self.score_item(query_embedding, item, strategy)
            except Exception as e:
                logger.warning("Embedding comparison skipped: %s", e)
                continue

            item["embedding_score"] = similarity
            if similarity >= threshold:
                filtered.append(item)

        filtered.sort(key=lambda x: x["embedding_score"], reverse=True)
        return filtered

    def batch_filter(self, query: str, results_by_language: dict[str, list[dict]],
                     thresholds: dict[str, float] = None) -> dict[str, list[dict]]:
        """Filter each language's results with its own threshold."""
        thresholds = thresholds or {}
        return {
            lang: self.filter_results(query, lst, threshold=thresholds.get(lang))
            for lang, lst in results_by_language.items()
        }
