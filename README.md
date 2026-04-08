# MYEXA - Advanced Search Engine with Exa API

Multi-language search engine with embedding-based filtering, OCR support, and custom site database.

## Features

- 🌐 Multi-language search (EN, DE, IT)
- 🤖 Embedding-based result filtering (sentence-transformers)
- 📄 OCR support (PyPDF2 + Tesseract)
- 💾 SQLite database for results and custom sites
- 🔍 Search in custom site database
- 📊 Result indexing and relevance scoring
- 🎨 Vue 3 web interface on port 3005
- ⚡ FastAPI backend

## Project Structure

```
MYEXA/
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── requirements.txt
│   ├── api/
│   │   ├── search.py
│   │   ├── database.py
│   │   └── translator.py
│   ├── services/
│   │   ├── exa_service.py
│   │   ├── embedding.py
│   │   ├── indexing.py
│   │   ├── ocr_service.py
│   │   └── site_db.py
│   └── models/
│       └── schemas.py
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── database/
│   └── myexa.db
├── .gitignore
├── .env.example
└── README.md
```

## Installation

```bash
pip install -r backend/requirements.txt
```

## Running

```bash
python backend/app.py
```

Visit: http://localhost:3005
