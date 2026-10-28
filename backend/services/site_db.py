
import logging

from api.database import Database

logger = logging.getLogger(__name__)


class SiteDBService:
    def __init__(self):
        self.db = Database()

    def add_site(self, url: str, title: str, category: str = None, tags: str = None) -> bool:
        try:
            self.db.add_custom_site(url, title, category, tags)
            return True
        except Exception as e:
            logger.error("Error adding site: %s", e)
            return False

    def get_all_sites(self) -> list[dict]:
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
        except Exception as e:
            logger.error("Error getting sites: %s", e)
            return []

    def search_in_custom_db(self, query: str) -> list[dict]:
        """Search the custom sites word by word, ranked by the number of hits.

        The whole query phrase had to be a substring before, so a real
        multi-word query ("python async programming") never matched anything.
        Every word of the query is looked for on its own in the URL, the title
        and the tags; the site with the most matched words comes first.
        """
        sites = self.get_all_sites()

        # Words of one or two characters are noise — "c" is a substring of
        # "docs" and matches everything.
        words = [word for word in query.lower().split() if len(word) > 2]
        if not words:
            return []

        results = []
        for site in sites:
            haystack = " ".join([
                site.get("url") or "",
                site.get("title") or "",
                site.get("tags") or "",
            ]).lower()

            matched = {word for word in words if word in haystack}
            if not matched:
                continue

            entry = dict(site)
            entry["match_count"] = len(matched)
            results.append(entry)

        # More matched words first; the rest keeps the database order.
        results.sort(key=lambda item: item["match_count"], reverse=True)
        return results

    def add_from_search_result(self, url: str, title: str, category: str = "search_result") -> bool:
        return self.add_site(url, title, category)

    def get_site_urls(self) -> list[str]:
        sites = self.get_all_sites()
        return [site["url"] for site in sites]

    def delete_site(self, site_id: int) -> bool:
        try:
            return self.db.delete_custom_site(site_id)
        except Exception as e:
            logger.error("Error deleting site: %s", e)
            return False
