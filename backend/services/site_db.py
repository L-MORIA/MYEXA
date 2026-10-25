import logging
from typing import List, Dict
from api.database import Database

logger = logging.getLogger(__name__)

class SiteDBService:
    def __init__(self):
        self.db = Database()

    def add_site(self, url: str, title: str, category: str = None, tags: str = None) -> bool:
        try:
            self.db.add_custom_site(url, title, category, tags)
            return True
        except Exception:
            logger.exception("Error adding site")
            return False

    def get_all_sites(self) -> List[Dict]:
        try:
            sites = self.db.get_custom_sites()
            return [
                {
                    "id": row["id"],
                    "url": row["url"],
                    "title": row["title"],
                    "category": row["category"],
                    "tags": row["tags"],
                    "added_at": row["added_at"]
                }
                for row in sites
            ]
        except Exception:
            logger.exception("Error getting sites")
            return []

    def search_in_custom_db(self, query: str) -> List[Dict]:
        sites = self.get_all_sites()
        results = []

        query_lower = query.lower()
        for site in sites:
            if (query_lower in site["url"].lower() or
                query_lower in site["title"].lower() or
                query_lower in (site.get("tags") or "").lower()):
                results.append(site)

        return results

    def add_from_search_result(self, url: str, title: str, category: str = "search_result") -> bool:
        return self.add_site(url, title, category)

    def get_site_urls(self) -> List[str]:
        sites = self.get_all_sites()
        return [site["url"] for site in sites]

    def delete_site(self, site_id: int) -> bool:
        try:
            return self.db.delete_custom_site(site_id)
        except Exception:
            logger.exception("Error deleting site")
            return False
