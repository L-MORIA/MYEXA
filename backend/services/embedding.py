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
        return self.model.encode(text, convert_to_tensor=True, show_progress_bar=False)

    @torch.no_grad()
    def _get_embeddings(self, texts: list[str]) -> list:
        """Encode many texts in one model call.

        One forward pass per text made the relevance filter the slowest stage
        of a search: 40 results meant 40 model calls. The model batches the
        texts internally, so one call with the whole list is several times
        faster.
        """
        if not texts:
            return []
        encoded = self.model.encode(
            texts, convert_to_tensor=True, show_progress_bar=False
        )
        return list(encoded)

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

        return self._blend(
            query_embedding,
            self._get_embedding(title),
            self._get_embedding(snippet),
        )

    def _blend(self, query_embedding, title_embedding, snippet_embedding) -> float:
        """Combine the two pre-computed similarities with the configured weights.

        Kept separate from ``_score_blend`` so the batched and the per-item
        path use exactly the same formula.
        """
        if title_embedding is None:
            return self.calculate_similarity(query_embedding, snippet_embedding)
        if snippet_embedding is None:
            return self.calculate_similarity(query_embedding, title_embedding)
        return (
            self.calculate_similarity(query_embedding, title_embedding)
            * Config.RELEVANCE_TITLE_WEIGHT
            + self.calculate_similarity(query_embedding, snippet_embedding)
            * Config.RELEVANCE_SNIPPET_WEIGHT
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

        strategy = strategy or Config.RELEVANCE_STRATEGY

        # Items without any text carry no signal and are skipped — the same
        # rule the per-item path applies.
        candidates = [
            item for item in items
            if self._title_text(item) or self._snippet_text(item)
        ]

        scores = self._score_candidates(query_embedding, candidates, strategy)

        filtered = []
        for item, similarity in zip(candidates, scores, strict=True):
            if similarity is None:
                continue

            item["embedding_score"] = similarity
            if similarity >= threshold:
                filtered.append(item)

        filtered.sort(key=lambda x: x["embedding_score"], reverse=True)
        return filtered

    def _score_candidates(self, query_embedding, items: list[dict],
                          strategy: str) -> list:
        """Score every candidate, batching the model calls where possible."""
        if strategy != "chunk":
            batched = self._score_batched(query_embedding, items, strategy)
            if batched is not None:
                return batched
        return self._score_one_by_one(query_embedding, items, strategy)

    def _score_batched(self, query_embedding, items: list[dict], strategy: str):
        """Score all items with a single batched model call.

        Returns ``None`` when the batch cannot be used, so the caller falls
        back to the per-item path. The fallback matters: a single broken
        text must not take the whole batch down, and the model may not
        return one embedding per text at all.
        """
        texts = []
        slots = []  # (item index, "title" | "snippet")
        for index, item in enumerate(items):
            title = self._title_text(item)
            snippet = self._snippet_text(item)
            if strategy == "title":
                texts.append(title)
                slots.append((index, "title"))
                continue
            if title:
                texts.append(title)
                slots.append((index, "title"))
            if snippet:
                texts.append(snippet)
                slots.append((index, "snippet"))

        if not texts:
            return [None] * len(items)

        try:
            embeddings = self._get_embeddings(texts)
        except Exception as e:
            logger.warning("Batched embedding failed, falling back to per-item scoring: %s", e)
            return None

        if len(embeddings) != len(texts):
            # The model did not return one embedding per text — do not guess
            # which one belongs where.
            logger.warning(
                "Batched embedding returned %d vectors for %d texts — using the per-item path",
                len(embeddings), len(texts),
            )
            return None

        per_item: dict[int, dict] = {}
        for (index, kind), embedding in zip(slots, embeddings, strict=True):
            per_item.setdefault(index, {})[kind] = embedding

        scores = []
        for index in range(len(items)):
            item_embeddings = per_item.get(index) or {}
            title_embedding = item_embeddings.get("title")
            snippet_embedding = item_embeddings.get("snippet")
            if title_embedding is None and snippet_embedding is None:
                scores.append(None)
            elif strategy == "title":
                scores.append(self.calculate_similarity(query_embedding, title_embedding))
            else:
                scores.append(
                    self._blend(query_embedding, title_embedding, snippet_embedding)
                )
        return scores

    def _score_one_by_one(self, query_embedding, items: list[dict],
                          strategy: str) -> list:
        """Score each item on its own — one broken text drops only itself."""
        scores = []
        for item in items:
            try:
                scores.append(self.score_item(query_embedding, item, strategy))
            except Exception as e:
                logger.warning("Embedding comparison skipped: %s", e)
                scores.append(None)
        return scores

    def batch_filter(self, query: str, results_by_language: dict[str, list[dict]],
                     thresholds: dict[str, float] = None) -> dict[str, list[dict]]:
        """Filter each language's results with its own threshold."""
        thresholds = thresholds or {}
        return {
            lang: self.filter_results(query, lst, threshold=thresholds.get(lang))
            for lang, lst in results_by_language.items()
        }
