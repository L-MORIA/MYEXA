from exa_py import Exa
from config import Config
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class ExaService:
    def __init__(self):
        self.exa = Exa(Config.EXA_API_KEY)
    
    def search(self, query: str, num_results: int = 10, language: str = "en") -> List[Dict]:
        """Search using Exa API"""
        try:
            result = self.exa.search(
                query,
                num_results=num_results,
                type="auto",
                contents={
                    "highlights": {
                        "max_characters": 4000
                    }
                }
            )
            
            results = []
            for item in result.results:
                results.append({
                    "url": item.url,
                    "title": item.title,
                    "highlights": item.highlights[0] if item.highlights else "",
                    "score": item.highlightScores[0] if item.highlightScores else 0.0,
                    "language": language
                })
            
            return results
        except Exception as e:
            logger.error(f"Exa search error: {e}")
            return []
    
    def search_multiple_languages(self, query: str, languages: List[str], 
                                 num_results: int = 10) -> Dict[str, List[Dict]]:
        """Search in multiple languages"""
        results = {}
        for lang in languages:
            results[lang] = self.search(query, num_results, lang)
        return results
    
    def get_contents(self, urls: List[str]) -> List[Dict]:
        """Get full contents from URLs"""
        try:
            result = self.exa.get_contents(
                urls,
                text={"max_characters": 20000}
            )
            
            contents = []
            for item in result.results:
                contents.append({
                    "url": item.url,
                    "title": item.title,
                    "text": item.text if hasattr(item, 'text') else ""
                })
            
            return contents
        except Exception as e:
            logger.error(f"Get contents error: {e}")
            return []
