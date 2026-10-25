# MYEXA — Advanced Search Engine

Multi-language search engine with embedding-based filtering, OCR support, and custom site database.

## Features

- Multi-language search (EN, DE, IT) via Exa API
- Automatic query translation (Google Translate AJAX, no key required)
- Embedding-based relevance filtering (sentence-transformers all-MiniLM-L6-v2)
- OCR support (PyPDF2 + Tesseract) for PDF and images
- SQLite database for results and custom sites
- Relevance indexing (domain authority, freshness, custom boost)
- Vue 3 web interface on port 3005
- FastAPI async backend
- Desktop launcher with auto-start and health-check polling

## Quick Start

```bash
pip install -r backend/requirements.txt
python backend/app.py
```

Visit **http://localhost:3005**

Or double-click `MYEXA.lnk` on the desktop.

## Project Structure

```
MYEXA/
├── backend/
│   ├── app.py                  # FastAPI application (routes, CORS, static)
│   ├── config.py               # Configuration (.env, logging)
│   ├── requirements.txt        # Python dependencies
│   ├── api/
│   │   ├── database.py         # SQLite with context manager + row_factory
│   │   └── translator.py       # Google Translate AJAX + LibreTranslate fallback
│   ├── services/
│   │   ├── exa_service.py      # Exa API via direct HTTP requests
│   │   ├── embedding.py        # sentence-transformers encoding + filtering
│   │   ├── indexing.py         # Relevance index calculation
│   │   ├── ocr_service.py      # PDF/image text extraction
│   │   └── site_db.py          # Custom site CRUD
│   └── models/
│       └── schemas.py          # Pydantic models
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
- **ML:** sentence-transformers 3.4.1, PyTorch 2.11
- **Search:** Exa API (direct HTTP)
- **Translation:** Google Translate AJAX (free, no key)
- **OCR:** PyPDF2, Tesseract, pdf2image
- **Frontend:** Vue 3 (CDN), CSS
