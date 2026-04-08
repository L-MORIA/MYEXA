# MYEXA - Advanced Multi-Language Search Engine

Advanced search engine powered by Exa API with embedding-based filtering, OCR support, and custom site database management.

## 🚀 Features

- **Multi-Language Search** - Search in English, German, and Italian simultaneously
- **Embedding-Based Filtering** - Uses sentence-transformers for semantic relevance scoring
- **Smart Indexing** - Relevance index (0-100) based on multiple factors:
  - Embedding similarity (40%)
  - Domain authority (20%)
  - Content freshness (15%)
  - Language match (15%)
  - Custom site boost (10%)
- **OCR Support** - Extract text from PDF and images (PyPDF2 + Tesseract)
- **Custom Site Database** - Build and search your own curated site collection
- **Vue 3 Web Interface** - Modern, responsive UI on port 3005
- **FastAPI Backend** - High-performance async API
- **SQLite Database** - Persistent storage for results and custom sites

## 📋 Project Structure

```
MYEXA/
├── backend/
│   ├── app.py                    # FastAPI main application
│   ├── config.py                 # Configuration management
│   ├── requirements.txt           # Python dependencies
│   ├── api/
│   │   ├── search.py             # Search endpoints
│   │   ├── database.py           # Database operations
│   │   └── translator.py         # Multi-language translation
│   ├── services/
│   │   ├── exa_service.py        # Exa API integration
│   │   ├── embedding.py          # Embedding & filtering
│   │   ├── indexing.py           # Result ranking & indexing
│   │   ├── ocr_service.py        # OCR processing
│   │   └── site_db.py            # Custom site management
│   └── models/
│       └── schemas.py            # Pydantic data models
├── frontend/
│   ├── index.html                # Main HTML page
│   ├── style.css                 # Styling
│   └── script.js                 # Vue 3 application
├── database/
│   └── myexa.db                  # SQLite database (auto-created)
├── run.bat                       # Windows launcher
├── run.sh                        # Linux/Mac launcher
├── .env.example                  # Environment variables template
├── .gitignore                    # Git ignore rules
└── README.md                     # This file
```

## 🔧 Installation

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- Tesseract OCR (optional, for image/PDF OCR)

### Windows

1. Clone or download the project
2. Navigate to the project directory
3. Run the launcher:
```bash
run.bat
```

### Linux/Mac

1. Clone or download the project
2. Navigate to the project directory
3. Make the script executable:
```bash
chmod +x run.sh
```
4. Run the launcher:
```bash
./run.sh
```

### Manual Installation

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r backend/requirements.txt
```

3. Create `.env` file:
```bash
cp .env.example .env
```

4. Add your Exa API key to `.env`:
```
EXA_API_KEY=your_api_key_here
```

5. Start the application:
```bash
python backend/app.py
```

## 🌐 Usage

1. Open browser: `http://localhost:3005`
2. Enter search query
3. Select languages (EN, DE, IT)
4. Configure options:
   - Filter by Relevance (embedding-based)
   - Search Custom DB
   - Number of results
5. Click Search
6. View results with relevance scores
7. Add interesting results to Custom Database
8. Manage custom sites in the database section

## 📄 OCR Features

Upload PDF or image files to extract text:
- **PDF**: Tries PyPDF2 first, falls back to Tesseract
- **Images**: Uses Tesseract OCR
- Supports: JPG, PNG, BMP, TIFF, PDF

## 💾 Database

### Search Results Table
- Stores all search results with relevance scores
- Indexed by query and relevance
- Includes language and source information

### Custom Sites Table
- User-curated collection of websites
- Supports categories and tags
- Boosts relevance in search results

### Search History Table
- Tracks all searches performed
- Records languages used and result count

## 🔍 Filtering & Indexing Rules

**Relevance Index Calculation:**
```
Index = (embedding_score × 0.40) +
        (domain_authority × 0.20) +
        (content_freshness × 0.15) +
        (language_match × 0.15) +
        (custom_boost × 0.10)
```

**Domain Authority Scoring:**
- Trusted domains (GitHub, StackOverflow, etc.): 1.0
- HTTPS sites: 0.7
- Other sites: 0.5

**Content Freshness:**
- 0-7 days old: 1.0
- 8-30 days: 0.8
- 31-90 days: 0.6
- 91-365 days: 0.4
- 365+ days: 0.2

## 🔐 Environment Variables

Create `.env` file with:
```
EXA_API_KEY=your_exa_api_key
DATABASE_PATH=./database/myexa.db
LOG_LEVEL=INFO
PORT=3005
HOST=0.0.0.0
TESSERACT_PATH=tesseract  # Path to Tesseract executable
```

## 📚 API Endpoints

### Search
- **POST** `/api/search` - Perform multi-language search
  ```json
  {
    "query": "search term",
    "languages": ["en", "de", "it"],
    "num_results": 10,
    "filter_by_relevance": true,
    "search_custom_db": true
  }
  ```

### OCR
- **POST** `/api/ocr` - Process PDF/image file
  - Form data: `file`, `language`

### Custom Sites
- **GET** `/api/custom-sites` - Get all custom sites
- **POST** `/api/custom-sites/add` - Add new site
- **DELETE** `/api/custom-sites/{url}` - Delete site

### Health
- **GET** `/api/health` - Health check

## 🛠️ Technologies

**Backend:**
- FastAPI - Modern web framework
- SQLAlchemy - ORM
- sentence-transformers - Embedding model
- exa-py - Exa API client
- PyPDF2 - PDF text extraction
- pytesseract - OCR engine
- google-cloud-translate - Translation API

**Frontend:**
- Vue 3 - Progressive framework
- Vanilla CSS - Styling
- Fetch API - HTTP requests

**Database:**
- SQLite - Lightweight database

## 🚀 Performance Tips

1. **Embedding Model**: Uses `all-MiniLM-L6-v2` (lightweight, fast)
2. **Caching**: Results are cached in SQLite
3. **Batch Processing**: Multiple language searches in parallel
4. **Lazy Loading**: OCR processes files on-demand

## 🐛 Troubleshooting

### Port 3005 already in use
Change PORT in `.env` file

### Tesseract not found
Install Tesseract OCR:
- **Windows**: Download from https://github.com/UB-Mannheim/tesseract/wiki
- **Linux**: `sudo apt-get install tesseract-ocr`
- **Mac**: `brew install tesseract`

### API Key errors
Ensure `EXA_API_KEY` is set in `.env` file

### Database errors
Delete `database/myexa.db` to reset database

## 📝 Git Repository

Local Git repository initialized at project root:
```bash
git log          # View commit history
git status       # Check status
git add .        # Stage changes
git commit -m "message"  # Commit changes
```

## 📄 License

MYEXA - Advanced Search Engine (2026)

## 🤝 Contributing

To add features:
1. Create feature branch
2. Make changes
3. Test thoroughly
4. Commit with clear messages
5. Push to repository

## 📞 Support

For issues or questions:
1. Check troubleshooting section
2. Review API documentation
3. Check Exa API docs: https://docs.exa.ai

---

**Version**: 1.0.0  
**Last Updated**: 2026-04-08  
**Status**: Production Ready
