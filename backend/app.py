import asyncio
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

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))

from api.database import Database
from api.translator import Translator
from config import Config
from models.schemas import SearchQuery
from services.embedding import EmbeddingService
from services.exa_service import ExaError, ExaService
from services.indexing import IndexingService
from services.language_detector import LanguageDetector
from services.ocr_service import OCRService
from services.search_provider import ProviderError, ProviderUnavailable
from services.searxng_service import SearxngError, SearxngService
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
searxng_service = SearxngService()
embedding_service = EmbeddingService()
indexing_service = IndexingService()
language_detector = LanguageDetector()
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
        # The HTML must never be cached: it references the versioned asset URLs
        # (?v=N). A cached index.html keeps pointing at the previous version,
        # so frontend updates only arrive after a manual hard reload.
        return FileResponse(
            frontend_index,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return {"message": "MYEXA API running on port 3005"}

@app.get("/favicon.ico")
async def favicon():
    favicon_path = os.path.join(frontend_path, "favicon.svg")
    if os.path.exists(favicon_path):
        return FileResponse(
            favicon_path,
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return RedirectResponse(url="/static/favicon.svg")

@app.post("/api/search")
async def search(query_data: SearchQuery):
    """Search with multi-language support and filtering"""
    try:
        query = query_data.query
        languages = query_data.languages or [Config.SOURCE_LANGUAGE]
        num_results = query_data.num_results

        # Reject unknown language codes explicitly. Silently accepting them
        # produced a "Russian" search labelled as another language, with no
        # translation and no localisation.
        unsupported = [lang for lang in languages if not Config.is_supported(lang)]
        if unsupported:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported language(s): {', '.join(sorted(set(unsupported)))}. "
                    f"Supported: {', '.join(Config.SUPPORTED_LANGUAGES)}"
                ),
            )

        # Translate query to all requested languages. ``translations`` holds the
        # translated query per language (and the original under "original").
        #
        # The translation runs in a worker thread: it is a blocking network
        # round-trip, and doing it on the event loop froze the whole server
        # for the duration of the request.
        translations = await asyncio.to_thread(
            translator.translate_to_multiple, query, languages
        )

        # Search the primary provider in each language using the *translated*
        # query. Exa has no native lang param, so the query is localised with
        # `userLocation` (country code). A hard `includeDomains` filter is NOT
        # used by default: it restricts results to those domains only, which
        # confined the Russian corpus to five sites while English searched
        # the whole web.
        #
        # The languages are searched concurrently — they are independent, and
        # the sequential version took up to 60s for four languages.
        async def _search_language(lang: str):
            search_query = translations.get(lang) or translations.get("original") or query
            country = Config.language_country(lang)
            try:
                results = await asyncio.to_thread(
                    exa_service.search, search_query, num_results, lang, country=country
                )
                return lang, results, "exa", None
            except ExaError as e:
                primary_error = str(e)

            # The primary provider failed — blocked, unreachable, out of credit.
            # A local SearXNG instance can still answer, so one failed
            # provider does not have to mean "no search".
            if not searxng_service.is_configured():
                raise ProviderUnavailable(primary_error)

            logger.warning(
                "Primary provider failed for %s (%s) — falling back to SearXNG",
                lang, primary_error,
            )
            try:
                results = await asyncio.to_thread(
                    searxng_service.search, search_query, num_results, lang, country=country
                )
            except SearxngError as e:
                raise ProviderUnavailable(f"exa: {primary_error}; searxng: {e}") from e
            return lang, results, "searxng", primary_error

        settled = await asyncio.gather(
            *[_search_language(lang) for lang in languages],
            return_exceptions=True,
        )

        all_results = {}
        provider_errors = {}
        provider_used = {}
        fallback_reasons = {}
        for lang, outcome in zip(languages, settled, strict=True):
            if isinstance(outcome, BaseException):
                if isinstance(outcome, ProviderError):
                    logger.error("Search provider failed for %s: %s", lang, outcome)
                    provider_errors[lang] = str(outcome)
                    all_results[lang] = []
                else:
                    # An unexpected error is a defect, not a provider outage.
                    # Reporting it as "the backend is down" would hide the
                    # cause, and its text could leak internals to the client.
                    raise outcome
            else:
                _, results, provider, fallback_reason = outcome
                all_results[lang] = results
                provider_used[lang] = provider
                if fallback_reason:
                    fallback_reasons[lang] = fallback_reason

        # A provider outage is remembered here and turned into a 503 at the
        # end — only if there is nothing at all to show. The custom database is
        # searched locally and keeps working without any network access, so a
        # total Exa outage must not take the local results down with it.
        if provider_errors:
            logger.error("Search provider failed: %s", provider_errors)

        # Detect the language of every result. This used to be a hardcoded
        # `language_score = 1.0` ("assume language already matched"), which was
        # only true while a domain filter pinned each language to a few sites.
        for lang, results in all_results.items():
            language_detector.annotate(results, lang)

        # Filter by embedding similarity using the *translated* query for each
        # language. Previously the original (Russian) query was compared against
        # German/Italian/English snippets via an English-only model, so the 0.5
        # threshold silently dropped every non-English result.
        #
        # The score blends the result title with a short snippet — not the full
        # highlights blob, which Exa builds by quoting the query back.
        meta = {}
        for lang in languages:
            meta[lang] = {"provider": provider_used.get(lang, "exa")}
            if lang in fallback_reasons:
                # The primary provider failed and the fallback answered. The
                # reason is reported, so the user can tell why the source
                # changed instead of guessing.
                meta[lang]["fallback_reason"] = fallback_reasons[lang]

        if query_data.filter_by_relevance:
            # The languages are filtered concurrently. Each filter runs the
            # embedding model over its own results, and the model releases
            # the GIL during the forward pass — so four languages in parallel
            # take far less time than one after another (measured: 4.33 s ->
            # 1.53 s for four languages).
            async def _filter_language(lang: str):
                translated_query = translations.get(lang) or query
                threshold = (
                    query_data.relevance_threshold
                    if query_data.relevance_threshold is not None
                    else Config.language_threshold(lang)
                )
                # The filter is CPU-bound and takes seconds — in a worker
                # thread, so the server keeps serving other requests meanwhile.
                filtered = await asyncio.to_thread(
                    embedding_service.filter_results,
                    translated_query, all_results[lang], threshold=threshold,
                )
                return lang, filtered, threshold

            filtered_outcomes = await asyncio.gather(
                *[_filter_language(lang) for lang in all_results]
            )
            for lang, filtered, threshold in filtered_outcomes:
                fetched = len(all_results[lang])
                all_results[lang] = filtered
                meta[lang].update({
                    "fetched": fetched,
                    "returned": len(filtered),
                    "filtered_out": bool(fetched) and not filtered,
                    "threshold": threshold,
                })

        # Drop results written in another language. When fewer than half of
        # the results match, all of them are kept and the mismatch is flagged.
        for lang, results in all_results.items():
            before = len(results)
            all_results[lang] = language_detector.filter_by_language(results)
            if lang in meta:
                meta[lang]["language_filtered"] = before - len(all_results[lang])
                meta[lang]["language_mismatched"] = sum(
                    1 for r in all_results[lang] if r.get("language_mismatch")
                )

        for lang, message in provider_errors.items():
            meta.setdefault(lang, {})["error"] = message

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
                    source=provider_used.get(lang, "exa")
                )

        # Search custom database if enabled. This works entirely offline, so it
        # is the only thing that can still answer a query while the search
        # provider is unreachable.
        if query_data.search_custom_db:
            custom_results = site_db_service.search_in_custom_db(query)
            ranked_results["custom_db"] = custom_results

        # Every language failed AND the local database has nothing either ->
        # the backend is down, not "no results".
        all_languages_failed = bool(provider_errors) and len(provider_errors) == len(languages)
        if all_languages_failed and not ranked_results.get("custom_db"):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Search backend unavailable: "
                    + "; ".join(f"{lang}: {msg}" for lang, msg in provider_errors.items())
                ),
            )

        # Save to history
        db.save_search_history(query, ",".join(languages), sum(len(r) for r in ranked_results.values()))

        return {
            "success": True,
            "query": query,
            "translations": translations,
            "results": ranked_results,
            "meta": meta,
            "total_results": sum(len(r) for r in ranked_results.values())
        }

    except HTTPException:
        # Validation errors (400) and provider outages (503) must keep their
        # own status code instead of being flattened into a generic 500.
        raise
    except Exception as e:
        logger.exception("Request failed")
        raise HTTPException(status_code=500, detail="Internal server error") from e

@app.post("/api/ocr")
async def ocr_process(
    file: UploadFile = File(...),
    language: str = Form("eng"),
    request: Request = None,
):
    """Extract the text of an uploaded PDF or image.

    The language may arrive as a form field (that is how the frontend sends
    it) or as a query parameter. Only the form field was read before, so the
    language chosen in the interface was silently ignored and a Russian scan
    was read with the English model.
    """
    if not isinstance(language, str):
        # A direct call (not through the app) leaves the Form object in place.
        language = "eng"

    query_params = getattr(request, "query_params", None)
    query_language = query_params.get("language") if query_params else None
    if query_language:
        language = query_language

    allowed_ext = {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    max_bytes = Config.MAX_UPLOAD_BYTES
    content_length = file.headers.get("content-length")
    if content_length:
        try:
            declared = int(content_length)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400, detail="Invalid Content-Length header"
            ) from None
        if declared > max_bytes:
            raise HTTPException(
                status_code=400, detail=f"File too large (max {max_bytes // (1024 * 1024)}MB)"
            )

    temp_path = None
    try:
        suffix = os.path.splitext(file.filename or "upload")[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            # The declared length is a hint, not a guarantee: the body itself
            # is measured while it is read, so a lying header cannot get a
            # huge file past the limit.
            written = 0
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File too large (max {max_bytes // (1024 * 1024)}MB)",
                    )
                tmp.write(chunk)
            temp_path = tmp.name

        result = ocr_service.process_file(temp_path, language)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("OCR processing failed")
        raise HTTPException(status_code=500, detail="OCR processing failed") from e
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
        logger.exception("Request failed")
        raise HTTPException(status_code=500, detail="Internal server error") from e

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
        logger.exception("Request failed")
        raise HTTPException(status_code=500, detail="Internal server error") from e

@app.delete("/api/custom-sites/{site_id:int}")
async def delete_custom_site(site_id: int):
    try:
        success = site_db_service.delete_site(site_id)
        return {
            "success": success,
            "message": "Site deleted" if success else "Failed to delete site"
        }
    except Exception as e:
        logger.exception("Request failed")
        raise HTTPException(status_code=500, detail="Internal server error") from e

@app.get("/api/languages")
async def get_languages():
    """Supported languages — the single source of truth for the frontend."""
    return {
        "success": True,
        "languages": [
            {
                "code": code,
                "label": entry["label"],
                "country": entry.get("country"),
                "default": code in Config.DEFAULT_LANGUAGES,
            }
            for code, entry in Config.LANGUAGES.items()
        ],
        "default": list(Config.DEFAULT_LANGUAGES),
    }


@app.get("/api/health")
async def health(deep: bool = False):
    """Health check.

    With ``?deep=true`` the external dependencies are actually probed, so a
    broken API key or a blocked network shows up as ``degraded`` instead of a
    cheerful "healthy".
    """
    status = {
        "status": "healthy",
        "version": "1.0.0",
        "port": Config.PORT,
        "embedding_model": Config.EMBEDDING_MODEL,
        "embedding_available": embedding_service._available,
        "language_detector_available": language_detector.available,
    }

    if not deep:
        return status

    checks = {}
    try:
        results = exa_service.search("health check", 1, "en", country="US")
        checks["exa"] = {"ok": True, "results": len(results)}
    except ExaError as e:
        checks["exa"] = {"ok": False, "error": str(e)}
    except Exception as e:
        checks["exa"] = {"ok": False, "error": str(e)}

    # The fallback provider is probed separately: the search may still work
    # through it even while the primary one is blocked.
    if searxng_service.is_configured():
        try:
            fallback_results = searxng_service.search("health check", 1, "en")
            checks["searxng"] = {"ok": True, "results": len(fallback_results)}
        except SearxngError as e:
            checks["searxng"] = {"ok": False, "error": str(e)}
        except Exception as e:
            checks["searxng"] = {"ok": False, "error": str(e)}
    else:
        checks["searxng"] = {"ok": False, "skipped": True, "error": "fallback disabled"}

    checks["exa_api_key_present"] = bool(Config.EXA_API_KEY)

    status["checks"] = checks
    if checks["exa"]["ok"]:
        status["active_provider"] = "exa"
    elif checks.get("searxng", {}).get("ok"):
        # The primary provider is down, the search itself still works.
        status["status"] = "degraded"
        status["active_provider"] = "searxng"
        status["search_available"] = True
    else:
        status["status"] = "degraded"
        status["search_available"] = False
    return status

if __name__ == "__main__":
    import uvicorn

    # Write the PID so the launcher can stop exactly this server instead of
    # killing every python.exe on the machine.
    pid_file = os.path.join(os.path.dirname(Config.DATABASE_PATH), "myexa.pid")
    try:
        os.makedirs(os.path.dirname(pid_file), exist_ok=True)
        with open(pid_file, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
    except OSError as e:
        logger.warning("Could not write PID file %s: %s", pid_file, e)

    try:
        uvicorn.run(app, host=Config.HOST, port=Config.PORT)
    finally:
        try:
            os.remove(pid_file)
        except OSError:
            pass
