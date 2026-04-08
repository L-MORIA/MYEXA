from sentence_transformers import SentenceTransformer, util
from config import Config
from typing import List, Dict
import torch

class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer(Config.EMBEDDING_MODEL)
    
    def get_embedding(self, text: str):
        """Get embedding for text"""
        return self.model.encode(text, convert_to_tensor=True)
    
    def calculate_similarity(self, query_embedding, text_embedding) -> float:
        """Calculate cosine similarity between embeddings"""
        similarity = util.pytorch_cos_sim(query_embedding, text_embedding)
        return float(similarity[0][0])
    
    def filter_results(self, query: str, results: List[Dict], 
                      threshold: float = Config.RELEVANCE_THRESHOLD) -> List[Dict]:
        """Filter results based on embedding similarity"""
        query_embedding = self.get_embedding(query)
        filtered = []
        
        for result in results:
            text = result.get("highlights", "") or result.get("title", "")
            if not text:
                continue
            
            text_embedding = self.get_embedding(text)
            similarity = self.calculate_similarity(query_embedding, text_embedding)
            
            if similarity >= threshold:
                result["embedding_score"] = similarity
                filtered.append(result)
        
        # Sort by embedding score
        filtered.sort(key=lambda x: x["embedding_score"], reverse=True)
        return filtered
    
    def batch_filter(self, query: str, results_by_language: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """Filter results for multiple languages"""
        filtered_results = {}
        for lang, results in results_by_language.items():
            filtered_results[lang] = self.filter_results(query, results)
        return filtered_results
