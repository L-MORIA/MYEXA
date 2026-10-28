# MYEXA Project Overview

## Status: Operational

**Location:** `C:\MYEXA`  
**Version:** 1.0.0  
**Date:** 2026-05-15  
**Python:** 3.14  

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MYEXA ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Vue 3 Web Interface (Port 3005)              │  │
│  │    Search · OCR Upload · Custom Sites Management     │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ↓ HTTP                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              FastAPI Backend                          │  │
│  │  POST /api/search · POST /api/ocr · CRUD /sites      │  │
│  │  GET  /api/health · GET  / (frontend)                │  │
│  │  Favicon /static/ · CORS restricted                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ↓                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Services Layer                                      │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │  │
│  │  │ Exa API  │ │Embedding │ │Indexing  │ │  OCR   │ │  │
│  │  │(direct   │ │(sentence-│ │(relevance│ │PyPDF2 +│ │  │
│  │  │ HTTP)    │ │transform)│ │index)    │ │Tesseract│ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │  │
│  │  ┌──────────┐ ┌──────────┐                           │  │
│  │  │Translate │ │ Site DB  │                           │  │
│  │  │(Google   │ │ (CRUD)   │                           │  │
│  │  │ AJAX)    │ │          │                           │  │
│  │  └──────────┘ └──────────┘                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ↓                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  SQLite Database                                      │  │
│  │  search_results · custom_sites · search_history       │  │
│  │  (context manager + row_factory for safety)           │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ↓                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  External APIs                                       │  │
│  │  Exa (search) · Tesseract (local OCR)                 │  │
│  │  Yandex Translate (primary) + Google AJAX (fallback)  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Key Metrics

| Metric | Value |
|--------|-------|
| Backend source files | 10 |
| Test files | 9 (129 tests) |
| Frontend files | 4 (incl. favicon) |
| API endpoints | 8 (incl. /static mount) |
| Database tables | 3 (+ index on search_results.query) |
| Runtime dependencies | 13 (dead exa-py/sqlalchemy/google-cloud-translate removed) |
| Languages | 4 (RU, EN, DE, IT) |
| OCR formats | 5 (PDF, JPG, PNG, BMP, TIFF) |

## Data Flow

### Search
```
Query → Validate (422 on bad input) → Translate (Yandex/Google, LRU cache) → Exa API (per language)
  → Embedding filter (sentence-transformers, optional)
  → Relevance index (domain · freshness · custom boost)
  → Save to DB → Return to UI
```

### OCR
```
Upload → Validate extension + size → tempfile safe path
  → PDF? Try PyPDF2, fallback Tesseract → Image? Tesseract
  → Return text → Clean up temp file
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Frontend HTML |
| GET | `/favicon.ico` | SVG favicon |
| POST | `/api/search` | Multi-language search |
| POST | `/api/ocr` | PDF/image OCR |
| GET | `/api/custom-sites` | List custom sites |
| POST | `/api/custom-sites/add` | Add site (JSON body) |
| DELETE | `/api/custom-sites/{id}` | Delete site by ID |
| GET | `/api/health` | Health check |
| GET | `/static/*` | Static files (CSS, JS, favicon) |

## Changes from Original (April 2026)

| Area | Original | Current |
|------|----------|---------|
| Python | 3.8+ | 3.14 (only version available) |
| sentence-transformers | 2.2.2 | 3.4.1 (fixes C-level crash on 3.14) |
| exa-py library | used directly | replaced with raw HTTP requests (library incompatible with API) |
| Translation | LibreTranslate / google-cloud-translate | Yandex Translate + Google AJAX fallback (free, no key) |
| Delete site | by URL (path param) | by ID (path param) |
| Add site | query params | JSON body (Pydantic model) |
| OCR temp path | `/tmp/{filename}` | `tempfile.NamedTemporaryFile` (Windows compatible) |
| CORS | `allow_origins=["*"]` | `["http://localhost:3005"]` |
| SQLite | raw connections | context manager + `row_factory=sqlite3.Row` |
| Logging | `print()` | `logging` throughout |
| File upload limit | none | 50MB |
| Favicon | missing (404) | SVG favicon at `/favicon.ico` |
| Threading | default | `torch.set_num_threads(1)` for stability |
| Desktop launcher | basic run.bat | health-check polling + browser auto-open + icon |
| Dependencies | 13 | 15 (added pdf2image, python-multipart) |

## Dependencies

```
fastapi>=0.115.0            uvicorn>=0.32.0
sentence-transformers>=3.4  torch>=2.9.0
PyPDF2==3.0.1               pytesseract>=0.3.10
Pillow>=11.2.0              pdf2image==1.17.0
python-multipart==0.0.25    requests==2.31.0
pydantic>=2.10.0            python-dotenv==1.0.0
```

Removed 2026-10-25 (never imported by the code): `exa-py`, `sqlalchemy`,
`google-cloud-translate`.

## Security Notes

- Binds to `127.0.0.1` by default (LAN only via explicit `HOST=0.0.0.0`)
- CORS restricted to `localhost:3005`
- File upload: extension whitelist + enforced 50MB body limit + 50-page PDF cap + `tempfile` (no path traversal)
- Request validation: blank queries / unknown languages / `num_results` outside 1–50 → 422
- SQL: fully parameterized queries (no injection)
- 500 responses are generic; details go to the server log only
- `.env` excluded via `.gitignore`
- No authentication (add if deploying publicly)

See SECURITY_AUDIT.md for the full 2026-10-25 audit.

## Quick Start

```bash
pip install -r backend/requirements.txt
python backend/app.py
```

Or double-click `MYEXA.lnk` on the desktop.

**Version:** 1.1.0 — Last updated: 2026-10-25
