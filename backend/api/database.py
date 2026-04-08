import sqlite3
from datetime import datetime
from typing import List, Optional
from config import Config

class Database:
    def __init__(self):
        self.db_path = Config.DATABASE_PATH
        self.init_db()
    
    def init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Search results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                content TEXT,
                relevance_score REAL,
                language TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Custom sites table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custom_sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                category TEXT,
                tags TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Search history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                languages TEXT,
                results_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_result(self, query: str, url: str, title: str, content: str, 
                   relevance_score: float, language: str, source: str):
        """Save search result to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO search_results 
                (query, url, title, content, relevance_score, language, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (query, url, title, content, relevance_score, language, source))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()
    
    def get_results(self, query: str, limit: int = 50) -> List[dict]:
        """Get search results from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM search_results 
            WHERE query = ? 
            ORDER BY relevance_score DESC 
            LIMIT ?
        ''', (query, limit))
        
        results = cursor.fetchall()
        conn.close()
        return results
    
    def add_custom_site(self, url: str, title: str, category: str = None, tags: str = None):
        """Add site to custom database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO custom_sites (url, title, category, tags)
                VALUES (?, ?, ?, ?)
            ''', (url, title, category, tags))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()
    
    def get_custom_sites(self) -> List[dict]:
        """Get all custom sites"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM custom_sites')
        results = cursor.fetchall()
        conn.close()
        return results
    
    def save_search_history(self, query: str, languages: str, results_count: int):
        """Save search to history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO search_history (query, languages, results_count)
            VALUES (?, ?, ?)
        ''', (query, languages, results_count))
        
        conn.commit()
        conn.close()
