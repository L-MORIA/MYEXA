import logging
import os
import sys
import tempfile

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

import torch
torch.set_num_threads(1)
try:
    torch.set_num_interop_threads(1)
except RuntimeError:
    pass

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from models.schemas import SearchQuery
from api.database import Database
from api.translator import Translator
from services.exa_service import ExaService
from services.embedding import EmbeddingService
from services.indexing import IndexingService
from services.ocr_service import OCRService
from services.site_db import SiteDBService

logger = logging.getLogger(__name__)


class AddSiteRequest(BaseModel):
    url: str
    title: str
    category: str | None = None
    tags: str | None = None


app = FastAPI(title="MYEXA", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3005"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database()
translator = Translator()
exa_service = ExaService()
embedding_service = EmbeddingService()
indexing_service = IndexingService()
ocr_service = OCRService()
site_db_service = SiteDBService()

logger.info("All services initialized")

backend_dir = os.path.dirname(os.path.abspath(__file__))
frontend_path = os.path.normpath(os.path.join(backend_dir, "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    logger.info("Static files mounted from %s", frontend_path)

@app.get("/")
async def root():
    frontend_index = os.path.join(frontend_path, "index.html")
    if os.path.exists(frontend_index):
        return FileResponse(frontend_index)
    return {"message": "MYEXA API running on port 3005"}

@app.get("/favicon.ico")
async def favicon():
    favicon_path = os.path.join(frontend_path, "favicon.svg")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/svg+xml")
    return RedirectResponse(url="/static/favicon.svg")

@app.post("/api/search")
async def search(query_data: SearchQuery):
    """Search with multi-language support and filtering"""
    try:
        query = query_data.query
        languages = query_data.languages or [Config.SOURCE_LANGUAGE]
        num_results = query_data.num_results

        # Translate query to all requested languages. ``translations`` holds the
        # translated query per language (and the original under "original").
        translations = translator.translate_to_multiple(query, languages)

        # Search Exa in each language using the *translated* query, biased toward
        # that language's national domains (Exa has no native lang param).
        all_results = {}
        for lang in languages:
            search_query = translations.get(lang) or translations.get("original") or query
            include_domains = Config.language_domains(lang)
            results = exa_service.search(
                search_query, num_results, lang, include_domains=include_domains
            )
            all_results[lang] = results

        # Filter by embedding similarity using the *translated* query for each
        # language. Previously the original (Russian) query was compared against
        # German/Italian/English snippets via an English-only model, so the 0.5
        # threshold silently dropped every non-English result.
        if query_data.filter_by_relevance:
            for lang, results in all_results.items():
                translated_query = translations.get(lang) or query
                all_results[lang] = embedding_service.filter_results(translated_query, results)

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
    allowed_ext = {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content_length = file.headers.get("content-length")
    if content_length and int(content_length) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    temp_path = None
    try:
        suffix = os.path.splitext(file.filename or "upload")[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            temp_path = tmp.name

        result = ocr_service.process_file(temp_path, language)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

@app.post("/api/custom-sites/add")
async def add_custom_site(site: AddSiteRequest):
    try:
        success = site_db_service.add_site(site.url, site.title, site.category, site.tags)
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

@app.delete("/api/custom-sites/{site_id:int}")
async def delete_custom_site(site_id: int):
    try:
        success = site_db_service.delete_site(site_id)
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
