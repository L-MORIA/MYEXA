from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from models.schemas import SearchQuery, OCRRequest
from api.database import Database
from api.translator import Translator
from services.exa_service import ExaService
from services.embedding import EmbeddingService
from services.indexing import IndexingService
from services.ocr_service import OCRService
from services.site_db import SiteDBService

app = FastAPI(title="MYEXA", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
db = Database()
translator = Translator()
exa_service = ExaService()
embedding_service = EmbeddingService()
indexing_service = IndexingService()
ocr_service = OCRService()
site_db_service = SiteDBService()

# Serve static files
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def root():
    """Serve main page"""
    return {"message": "MYEXA API running on port 3005"}

@app.post("/api/search")
async def search(query_data: SearchQuery):
    """Search with multi-language support and filtering"""
    try:
        query = query_data.query
        languages = query_data.languages
        num_results = query_data.num_results
        
        # Translate query to all languages
        translations = translator.translate_to_multiple(query, languages)
        
        # Search in all languages
        all_results = {}
        for lang in languages:
            search_query = translations.get(lang, query)
            results = exa_service.search(search_query, num_results, lang)
            all_results[lang] = results
        
        # Filter by embedding similarity
        if query_data.filter_by_relevance:
            all_results = embedding_service.batch_filter(query, all_results)
        
        # Get custom sites for boosting
        custom_site_urls = site_db_service.get_site_urls()
        
        # Rank results
        ranked_results = {}
        for lang, results in all_results.items():
            ranked_results[lang] = indexing_service.rank_results(results, custom_site_urls)
            
            # Save to database
            for result in ranked_results[lang]:
                db.save_result(
                    query=query,
                    url=result.get("url", ""),
                    title=result.get("title", ""),
                    content=result.get("highlights", ""),
                    relevance_score=result.get("relevance_index", 0.0),
                    language=lang,
                    source="exa"
                )
        
        # Search custom database if enabled
        if query_data.search_custom_db:
            custom_results = site_db_service.search_in_custom_db(query)
            ranked_results["custom_db"] = custom_results
        
        # Save to history
        db.save_search_history(query, ",".join(languages), sum(len(r) for r in ranked_results.values()))
        
        return {
            "success": True,
            "query": query,
            "translations": translations,
            "results": ranked_results,
            "total_results": sum(len(r) for r in ranked_results.values())
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ocr")
async def ocr_process(file: UploadFile = File(...), language: str = "eng"):
    """Process file with OCR (PDF or image)"""
    try:
        # Save uploaded file temporarily
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        
        # Process file
        result = ocr_service.process_file(temp_path, language)
        
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/custom-sites/add")
async def add_custom_site(url: str, title: str, category: str = None, tags: str = None):
    """Add site to custom database"""
    try:
        success = site_db_service.add_site(url, title, category, tags)
        return {
            "success": success,
            "message": "Site added" if success else "Failed to add site"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/custom-sites")
async def get_custom_sites():
    """Get all custom sites"""
    try:
        sites = site_db_service.get_all_sites()
        return {
            "success": True,
            "sites": sites,
            "count": len(sites)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/custom-sites/{url}")
async def delete_custom_site(url: str):
    """Delete site from custom database"""
    try:
        success = site_db_service.delete_site(url)
        return {
            "success": success,
            "message": "Site deleted" if success else "Failed to delete site"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "port": Config.PORT
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.HOST, port=Config.PORT)
