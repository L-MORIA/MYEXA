from typing import List, Dict
from api.database import Database

class SiteDBService:
    def __init__(self):
        self.db = Database()
    
    def add_site(self, url: str, title: str, category: str = None, tags: str = None) -> bool:
        """Add site to custom database"""
        try:
            self.db.add_custom_site(url, title, category, tags)
            return True
        except Exception as e:
            print(f"Error adding site: {e}")
            return False
    
    def get_all_sites(self) -> List[Dict]:
        """Get all custom sites"""
        try:
            sites = self.db.get_custom_sites()
            return [
                {
                    "id": site[0],
                    "url": site[1],
                    "title": site[2],
                    "category": site[3],
                    "tags": site[4],
                    "added_at": site[5]
                }
                for site in sites
            ]
        except Exception as e:
            print(f"Error getting sites: {e}")
            return []
    
    def search_in_custom_db(self, query: str) -> List[Dict]:
        """Search in custom site database"""
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
        """Add search result to custom database"""
        return self.add_site(url, title, category)
    
    def get_site_urls(self) -> List[str]:
        """Get all site URLs for boosting"""
        sites = self.get_all_sites()
        return [site["url"] for site in sites]
    
    def delete_site(self, url: str) -> bool:
        """Delete site from custom database"""
        try:
            conn = __import__('sqlite3').connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM custom_sites WHERE url = ?', (url,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting site: {e}")
            return False
