from fastapi import Body, FastAPI, File, HTTPException, UploadFile, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import sys
import tempfile

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from config import Config, validate_config, setup_logging
from models.schemas import SearchQuery, OCRRequest, CustomSite
from api.database import Database
from api.translator import Translator
from services.exa_service import ExaService
from services.embedding import EmbeddingService
from services.indexing import IndexingService
from services.ocr_service import OCRService
from services.site_db import SiteDBService

# Setup rate limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="MYEXA", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Setup logging
logger = setup_logging()

# Validate configuration at startup
validate_config()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
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

frontend_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

@app.get("/")
async def root():
    """Open web UI when frontend is present; otherwise API stub."""
    if os.path.isdir(frontend_path):
        return RedirectResponse(url="/static/index.html", status_code=302)
    return {"message": "MYEXA API running", "port": Config.PORT}

@app.post("/api/search")
@limiter.limit("10/minute")
async def search(request: Request, query_data: SearchQuery):
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
@limiter.limit("5/minute")
async def ocr_process(request: Request, file: UploadFile = File(...), language: str = "eng"):
    """Process file with OCR (PDF or image)"""
    suffix = ""
    if file.filename and "." in file.filename:
        suffix = "." + file.filename.rsplit(".", 1)[-1]

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            temp_path = tmp.name
        result = ocr_service.process_file(temp_path, language)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

@app.post("/api/custom-sites/add")
@limiter.limit("20/minute")
async def add_custom_site(
    request: Request,
    site: CustomSite | None = Body(default=None),
    url: str | None = None,
    title: str | None = None,
    category: str | None = None,
    tags: str | None = None,
):
    """Add site: JSON body (web UI) or query params ?url=&title= (curl / API.md)."""
    try:
        if site is not None:
            u, t, c, tg = site.url, site.title, site.category, site.tags
        elif url is not None and title is not None:
            u, t, c, tg = url, title, category, tags
        else:
            raise HTTPException(
                status_code=422,
                detail="Provide JSON body {url, title, ...} or query params url and title.",
            )
        success = site_db_service.add_site(u, t, c, tg)
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
@limiter.limit("20/minute")
async def delete_custom_site(request: Request, url: str):
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

# Mount static files last so /api/* and / are not shadowed (FastAPI/Starlette route order).
if os.path.isdir(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

if __name__ == "__main__":
    import errno
    import uvicorn

    try:
        print(
            f"MYEXA web UI: http://127.0.0.1:{Config.PORT}/  "
            f"(API: http://127.0.0.1:{Config.PORT}/api/health)"
        )
        uvicorn.run(app, host=Config.HOST, port=Config.PORT)
    except OSError as e:
        winerror = getattr(e, "winerror", None)
        if winerror == 10048 or e.errno == errno.EADDRINUSE:
            print(
                f"Port {Config.PORT} is already in use. "
                "Stop the other MYEXA instance or any program using this port (default is 3005)."
            )
            raise SystemExit(1) from e
        raise
