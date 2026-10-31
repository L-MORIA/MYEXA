import os
from datetime import datetime
from typing import List, Optional
from config import Config
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

logger = logging.getLogger(__name__)

Base = declarative_base()


class SearchResult(Base):
    __tablename__ = 'search_results'
    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String, nullable=False)
    url = Column(String, unique=True, nullable=False)
    title = Column(String)
    content = Column(Text)
    relevance_score = Column(Float)
    language = Column(String)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class CustomSite(Base):
    __tablename__ = 'custom_sites'
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, unique=True, nullable=False)
    title = Column(String)
    category = Column(String)
    tags = Column(String)
    added_at = Column(DateTime, default=datetime.utcnow)


class SearchHistory(Base):
    __tablename__ = 'search_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String, nullable=False)
    languages = Column(String)
    results_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class Database:
    def __init__(self):
        self.db_path = Config.DATABASE_PATH
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        # Create engine with connection pooling
        self.engine = create_engine(
            f'sqlite:///{self.db_path}',
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False
        )
        
        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.init_db()
    
    def init_db(self):
        """Initialize database tables"""
        Base.metadata.create_all(self.engine)
        logger.info("Database initialized successfully")
    
    @contextmanager
    def get_session(self):
        """Context manager for database sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def save_result(self, query: str, url: str, title: str, content: str, 
                   relevance_score: float, language: str, source: str):
        """Save search result to database"""
        with self.get_session() as session:
            try:
                result = SearchResult(
                    query=query,
                    url=url,
                    title=title,
                    content=content,
                    relevance_score=relevance_score,
                    language=language,
                    source=source
                )
                session.merge(result)  # merge handles duplicates
            except Exception as e:
                logger.error(f"Error saving result: {e}")
    
    def get_results(self, query: str, limit: int = 50) -> List[dict]:
        """Get search results from database"""
        with self.get_session() as session:
            try:
                results = session.query(SearchResult)\
                    .filter(SearchResult.query == query)\
                    .order_by(SearchResult.relevance_score.desc())\
                    .limit(limit)\
                    .all()
                
                return [
                    {
                        'id': r.id,
                        'query': r.query,
                        'url': r.url,
                        'title': r.title,
                        'content': r.content,
                        'relevance_score': r.relevance_score,
                        'language': r.language,
                        'source': r.source,
                        'created_at': r.created_at
                    }
                    for r in results
                ]
            except Exception as e:
                logger.error(f"Error getting results: {e}")
                return []
    
    def add_custom_site(self, url: str, title: str, category: str = None, tags: str = None):
        """Add site to custom database"""
        with self.get_session() as session:
            try:
                site = CustomSite(
                    url=url,
                    title=title,
                    category=category,
                    tags=tags
                )
                session.merge(site)
            except Exception as e:
                logger.error(f"Error adding custom site: {e}")
    
    def get_custom_sites(self) -> List[dict]:
        """Get all custom sites"""
        with self.get_session() as session:
            try:
                sites = session.query(CustomSite).all()
                return [
                    {
                        'id': s.id,
                        'url': s.url,
                        'title': s.title,
                        'category': s.category,
                        'tags': s.tags,
                        'added_at': s.added_at
                    }
                    for s in sites
                ]
            except Exception as e:
                logger.error(f"Error getting custom sites: {e}")
                return []
    
    def save_search_history(self, query: str, languages: str, results_count: int):
        """Save search to history"""
        with self.get_session() as session:
            try:
                history = SearchHistory(
                    query=query,
                    languages=languages,
                    results_count=results_count
                )
                session.add(history)
            except Exception as e:
                logger.error(f"Error saving search history: {e}")
