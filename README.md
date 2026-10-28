# MYEXA — Advanced Search Engine

Multi-language search engine with embedding-based filtering, OCR support, and custom site database.

## Features

- Multi-language search (RU, EN, DE, IT) via Exa API
- Automatic query translation (Yandex first, Google Translate AJAX fallback; no key required)
- Embedding-based relevance filtering (sentence-transformers paraphrase-multilingual-MiniLM-L12-v2)
- OCR support (PyPDF2 + Tesseract) for PDF and images, with upload size and page limits
- SQLite database for results and custom sites (auto-created on first start)
- Relevance indexing 0–1, shown as a percentage (embedding similarity, provider score, domain authority, freshness, language match, custom boost)
- Custom site database with word-by-word matching, ranked by hit count
- Input validation on all API endpoints (blank queries, unknown languages, oversized requests rejected)
- Vue 3 web interface on port 3005
- FastAPI async backend
- 129 automated tests (pytest) + GitHub Actions CI
- Desktop launcher with auto-start and health-check polling

## Quick Start

```bash
pip install -r backend/requirements.txt
python backend/app.py
```

Visit **http://localhost:3005**

Or double-click `MYEXA.lnk` on the desktop.

### Search providers

Exa is the primary search provider. When it is unreachable — Cloudflare
answers HTTP 403 for whole IP ranges — the search automatically falls back to a
local [SearXNG](https://docs.searxng.org/) instance, so queries keep working
and the frontend says which provider answered.

The fallback is a Docker container bound to `127.0.0.1:8080`:

```powershell
powershell -ExecutionPolicy Bypass -File docker\start-searxng.ps1   # start
powershell -ExecutionPolicy Bypass -File docker\stop-searxng.ps1    # stop
```

**Docker Desktop must be running**, otherwise the fallback cannot answer.
`GET /api/health?deep=true` reports the active provider and whether the
search is available.

## Project Structure

```
MYEXA/
├── backend/
│   ├── app.py                  # FastAPI application (routes, CORS, static)
│   ├── config.py               # Configuration (.env, logging)
│   ├── requirements.txt        # Python dependencies
│   ├── api/
│   │   ├── database.py         # SQLite with context manager + row_factory
│   │   └── translator.py       # Yandex Translate + Google AJAX fallback (LRU cache)
│   ├── services/
│   │   ├── exa_service.py      # Exa API via direct HTTP requests
│   │   ├── searxng_service.py  # SearXNG fallback provider
│   │   ├── search_provider.py  # Shared provider contract
│   │   ├── embedding.py        # sentence-transformers encoding + filtering
│   │   ├── indexing.py         # Relevance index calculation
│   │   ├── language_detector.py # Per-result language detection (ru/en/de/it)
│   │   ├── ocr_service.py      # PDF/image text extraction
│   │   └── site_db.py          # Custom site CRUD
│   ├── models/
│   │   └── schemas.py          # Pydantic models + input validation
│   └── tests/                  # 129 pytest tests (all externals mocked)
├── frontend/
│   ├── index.html              # Vue 3 SPA
│   ├── script.js               # Vue 3 app logic
│   ├── style.css               # Responsive styling
│   └── favicon.svg             # Brand favicon
├── database/                   # SQLite storage (auto-created)
├── .env                        # Environment variables
├── run.bat                     # Windows launcher with health-check
└── run.sh                      # Linux/Mac launcher
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve frontend |
| POST | `/api/search` | Multi-language search |
| POST | `/api/ocr` | PDF/image text extraction |
| GET | `/api/custom-sites` | List custom sites |
| POST | `/api/custom-sites/add` | Add site (JSON body) |
| DELETE | `/api/custom-sites/{id}` | Delete site by ID |
| GET | `/api/health` | Health check |

## Environment

```env
EXA_API_KEY=your_key_here
DATABASE_PATH=./database/myexa.db
LOG_LEVEL=INFO
PORT=3005
# 127.0.0.1 = local only (recommended); 0.0.0.0 exposes the API to the network
HOST=127.0.0.1
```

## Tech Stack

- **Backend:** Python 3.14, FastAPI, Uvicorn, SQLite
- **ML:** sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2), PyTorch
- **Search:** Exa API (direct HTTP)
- **Translation:** Yandex Translate + Google Translate AJAX fallback (free, no key)
- **OCR:** PyPDF2, Tesseract, pdf2image
- **Frontend:** Vue 3 (CDN), CSS
- **Testing:** pytest, pytest-asyncio, httpx; CI on GitHub Actions

## Testing

```bash
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cd backend && pytest
```
