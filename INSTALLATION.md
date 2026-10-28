# MYEXA — Installation & User Guide

Advanced multi-language search engine with embedding-based filtering, OCR, and custom site database.

## Features

- **Multi-Language Search** — Russian, English, German, Italian simultaneously via Exa API
- **Embedding-Based Filtering** — sentence-transformers for semantic relevance scoring
- **Smart Indexing** — relevance index (0–1, the frontend shows it as a percentage): embedding similarity (15%), provider relevance score (25%), domain authority (20%), freshness (15%), language match (15%), custom boost (10%)
- **OCR Support** — extract text from PDF and images (PyPDF2 + Tesseract)
- **Custom Site Database** — curated site collection with categories, tags and word-by-word matching ranked by hit count
- **Vue 3 Web Interface** — modern responsive UI on port 3005
- **FastAPI Backend** — high-performance async API
- **SQLite Database** — persistent storage

## Prerequisites

- **Python 3.14** (3.14 recommended; 3.11+ should work)
- **pip** (Python package manager)
- **Exa API key** — get one at https://exa.ai
- **Tesseract OCR** *(optional)* — for image/PDF OCR

## Installation

### 1. Clone or download the project

```bash
cd C:\MYEXA
```

### 2. Install dependencies

```bash
pip install -r backend/requirements.txt
```

**Note:** If you get a "Python 3.14" compatibility error, ensure you have the latest pip:
```bash
pip install --upgrade pip
```

### 3. Create configuration

```bash
copy .env.example .env
```

Edit `.env` and add your Exa API key:
```env
EXA_API_KEY=your_exa_api_key_here
DATABASE_PATH=./database/myexa.db
LOG_LEVEL=INFO
PORT=3005
# 127.0.0.1 = local only (recommended); 0.0.0.0 exposes the API to the network
HOST=127.0.0.1
```

### 4. Start the server

```bash
python backend/app.py
```

### 5. Open the interface

Visit **http://localhost:3005** in your browser.

## Desktop Launcher

Double-click `MYEXA.lnk` on your desktop. It will:

1. Install/check dependencies
2. Start the server in background
3. Poll `/api/health` until ready (~30-45s for model loading)
4. Open `http://localhost:3005` automatically
5. Stop the server when you close the window

## Usage

### Search

1. Enter a query in any language
2. Select languages (RU, EN, DE, IT)
3. Toggle options:
   - **Filter by Relevance** — semantic similarity filter
   - **Search Custom DB** — include your saved sites
   - Results count (1–50, enforced by the API)
4. Click **Search**
5. Browse results with relevance scores

### Tab Navigation

- **Русский / English / Deutsch / Italiano** — results per language
- **Custom DB** — your saved site collection

### OCR

1. Click "Choose File" (PDF, JPG, PNG, BMP, TIFF)
2. Click **Process OCR**
3. Extracted text appears in the search box

### Custom Sites

1. Fill in URL, Title, Category, Tags
2. Click **Add Site**
3. Sites boost relevance in future searches

## Architecture

```
┌─────────────────────────────────────┐
│        Vue 3 Web Interface          │
│  (index.html / script.js / style)   │
└──────────────┬──────────────────────┘
               │ HTTP (fetch)
┌──────────────▼──────────────────────┐
│       FastAPI Backend (3005)        │
│  ┌─────────┐ ┌───────┐ ┌────────┐  │
│  │ Search  │ │  OCR  │ │ Sites  │  │
│  └────┬────┘ └───────┘ └────────┘  │
│       │                              │
│  ┌────▼─────────────────────────┐   │
│  │       Services               │   │
│  │  Exa · Embedding · Indexing  │   │
│  │  OCR · Translator · SiteDB   │   │
│  └──────────────────────────────┘   │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      External APIs                  │
│  Exa API · Google Translate ·       │
│  Tesseract (local)                  │
└─────────────────────────────────────┘
```

## Database

The SQLite database at `database/myexa.db` contains three tables:

- **search_results** — cached search results with relevance scores
- **custom_sites** — user-curated site collection
- **search_history** — query log

Reset the database by deleting `database/myexa.db`.

## Troubleshooting

### Port 3005 already in use

```bash
taskkill /F /IM python.exe
```
Or change `PORT` in `.env`.

### Exa API errors

Verify your key in `.env`. Without a valid key the search endpoint still
responds 200 — Exa results are simply empty (check the server log for
`Exa API error 403`).

### Embedding model fails

The model downloads on first run (~90MB). Ensure internet access. If `[Errno 22]` occurs, set:
```python
torch.set_num_threads(1)
```
(already configured in `app.py`)

### Tesseract not found

Install from https://github.com/UB-Mannheim/tesseract/wiki

### Translation not working

Translation uses the Yandex browser endpoint first with the Google Translate
AJAX endpoint as fallback; neither requires a key. If both fail (e.g. no
network), the original query is used untranslated — search keeps working.
Translations are cached in memory (LRU, 1024 entries).

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | >=0.115.0 | Web framework |
| uvicorn | >=0.32.0 | ASGI server |
| sentence-transformers | >=3.4.0 | Embedding model |
| torch | >=2.9.0 | ML framework |
| PyPDF2 | 3.0.1 | PDF text extraction |
| pytesseract | >=0.3.10 | OCR engine |
| Pillow | >=11.2.0 | Image processing |
| pdf2image | 1.17.0 | PDF to image conversion (requires Poppler) |
| python-multipart | 0.0.25 | Form data parsing |
| requests | 2.31.0 | HTTP client |
| pydantic | >=2.10.0 | Data validation |
| python-dotenv | 1.0.0 | Environment variables |

Dev/test extras (see `requirements-dev.txt`): pytest, pytest-asyncio, httpx.

## Version

**1.1.0** — Last updated: 2026-10-25
