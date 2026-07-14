import logging
from sentence_transformers import SentenceTransformer, util
from config import Config
from typing import List, Dict
import torch

logger = logging.getLogger(__name__)


class EmbeddingService:
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

    def filter_results(self, query: str, items: List[Dict],
                      threshold: float = Config.RELEVANCE_THRESHOLD) -> List[Dict]:
        if not self._available:
            return items

        try:
            query_embedding = self._get_embedding(query)
        except Exception as e:
            logger.error("Embedding query failed: %s", e)
            self._available = False
            return items

        filtered = []
        for item in items:
            text = item.get("highlights", "") or item.get("title", "")
            if not text:
                continue

            try:
                text_embedding = self._get_embedding(text)
                similarity = self.calculate_similarity(query_embedding, text_embedding)
            except Exception as e:
                logger.warning("Embedding comparison skipped: %s", e)
                continue

            item["embedding_score"] = similarity
            if similarity >= threshold:
                filtered.append(item)

        if filtered:
            filtered.sort(key=lambda x: x["embedding_score"], reverse=True)
            return filtered
        for item in items:
            item["embedding_score"] = item.get("embedding_score", 0.0)
        return items

    def batch_filter(self, query: str, results_by_language: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        return {lang: self.filter_results(query, lst) for lang, lst in results_by_language.items()}