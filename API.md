# MYEXA API Documentation

## Overview

MYEXA is a FastAPI-based search engine that integrates with Exa API, providing multi-language search, embedding-based filtering, OCR capabilities, and custom site management.

## Base URL

```
http://localhost:3005/api
```

## Authentication

Currently, no authentication is required. In production, add API key validation.

---

## Endpoints

### 1. Search

**Endpoint:** `POST /api/search`

**Description:** Perform multi-language search with embedding-based filtering

**Request Body:**
```json
{
  "query": "machine learning",
  "languages": ["en", "de", "it"],
  "num_results": 10,
  "filter_by_relevance": true,
  "search_custom_db": true
}
```

**Parameters:**
- `query` (string, required): Search query
- `languages` (array, optional): Languages to search in. Default: ["en", "de", "it"]
- `num_results` (integer, optional): Number of results per language. Default: 10
- `filter_by_relevance` (boolean, optional): Apply embedding-based filtering. Default: true
- `search_custom_db` (boolean, optional): Include custom database results. Default: true

**Response:**
```json
{
  "success": true,
  "query": "machine learning",
  "translations": {
    "original": "machine learning",
    "en": "machine learning",
    "de": "maschinelles Lernen",
    "it": "apprendimento automatico"
  },
  "results": {
    "en": [
      {
        "url": "https://example.com/ml",
        "title": "Machine Learning Guide",
        "highlights": "Machine learning is...",
        "score": 0.95,
        "language": "en",
        "embedding_score": 0.87,
        "relevance_index": 85.5
      }
    ],
    "de": [...],
    "it": [...],
    "custom_db": [...]
  },
  "total_results": 30
}
```

**Status Codes:**
- `200`: Success
- `500`: Server error

---

### 2. OCR Processing

**Endpoint:** `POST /api/ocr`

**Description:** Extract text from PDF or image files

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Parameters:
  - `file` (file, required): PDF or image file
  - `language` (string, optional): OCR language code. Default: "eng"

**Supported Formats:**
- PDF: `.pdf`
- Images: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`

**Response:**
```json
{
  "text": "Extracted text content...",
  "confidence": 0.95,
  "method": "PyPDF2",
  "success": true
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:3005/api/ocr \
  -F "file=@document.pdf" \
  -F "language=eng"
```

**Status Codes:**
- `200`: Success
- `400`: Invalid file
- `500`: Processing error

---

### 3. Custom Sites - Get All

**Endpoint:** `GET /api/custom-sites`

**Description:** Retrieve all custom sites from database

**Response:**
```json
{
  "success": true,
  "sites": [
    {
      "id": 1,
      "url": "https://github.com",
      "title": "GitHub",
      "category": "development",
      "tags": "code,repository",
      "added_at": "2026-04-08T10:30:00"
    }
  ],
  "count": 1
}
```

**Status Codes:**
- `200`: Success
- `500`: Server error

---

### 4. Custom Sites - Add

**Endpoint:** `POST /api/custom-sites/add`

**Description:** Add a new site to custom database

**Query Parameters:**
- `url` (string, required): Website URL
- `title` (string, required): Site title
- `category` (string, optional): Category name
- `tags` (string, optional): Comma-separated tags

**Example:**
```bash
curl -X POST "http://localhost:3005/api/custom-sites/add?url=https://github.com&title=GitHub&category=development&tags=code,repository"
```

**Response:**
```json
{
  "success": true,
  "message": "Site added"
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid parameters
- `500`: Server error

---

### 5. Custom Sites - Delete

**Endpoint:** `DELETE /api/custom-sites/{url}`

**Description:** Remove site from custom database

**Parameters:**
- `url` (string, required, URL-encoded): Website URL to delete

**Example:**
```bash
curl -X DELETE "http://localhost:3005/api/custom-sites/https%3A%2F%2Fgithub.com"
```

**Response:**
```json
{
  "success": true,
  "message": "Site deleted"
}
```

**Status Codes:**
- `200`: Success
- `404`: Site not found
- `500`: Server error

---

### 6. Health Check

**Endpoint:** `GET /api/health`

**Description:** Check API health status

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "port": 3005
}
```

**Status Codes:**
- `200`: Healthy

---

## Data Models

### SearchQuery
```python
{
  "query": str,
  "languages": List[str] = ["en", "de", "it"],
  "num_results": int = 10,
  "filter_by_relevance": bool = True,
  "search_custom_db": bool = True
}
```

### SearchResult
```python
{
  "id": int,
  "query": str,
  "url": str,
  "title": str,
  "content": Optional[str],
  "relevance_score": float,
  "language": str,
  "source": str,  # "exa" or "custom_db"
  "created_at": datetime
}
```

### CustomSite
```python
{
  "url": str,
  "title": str,
  "category": Optional[str],
  "tags": Optional[str]
}
```

### OCRResult
```python
{
  "text": str,
  "confidence": float,
  "method": str,  # "PyPDF2", "Tesseract", or "Failed"
  "success": bool
}
```

---

## Error Handling

All errors return JSON with status code:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common Errors:**
- `400 Bad Request`: Invalid parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server-side error

---

## Rate Limiting

Currently no rate limiting. In production, implement:
- Per-IP rate limiting
- Per-API-key rate limiting
- Request queuing

---

## Examples

### Python

```python
import requests

# Search
response = requests.post(
    "http://localhost:3005/api/search",
    json={
        "query": "artificial intelligence",
        "languages": ["en", "de"],
        "num_results": 5
    }
)
results = response.json()

# Add custom site
response = requests.post(
    "http://localhost:3005/api/custom-sites/add",
    params={
        "url": "https://example.com",
        "title": "Example",
        "category": "reference"
    }
)

# OCR
with open("document.pdf", "rb") as f:
    files = {"file": f}
    response = requests.post(
        "http://localhost:3005/api/ocr",
        files=files,
        data={"language": "eng"}
    )
```

### JavaScript/Fetch

```javascript
// Search
const response = await fetch('/api/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'artificial intelligence',
    languages: ['en', 'de'],
    num_results: 5
  })
});
const results = await response.json();

// Get custom sites
const sites = await fetch('/api/custom-sites').then(r => r.json());

// Add site
await fetch('/api/custom-sites/add?url=https://example.com&title=Example');
```

### cURL

```bash
# Search
curl -X POST http://localhost:3005/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "artificial intelligence",
    "languages": ["en", "de"],
    "num_results": 5
  }'

# Get sites
curl http://localhost:3005/api/custom-sites

# Add site
curl -X POST "http://localhost:3005/api/custom-sites/add?url=https://example.com&title=Example"

# Delete site
curl -X DELETE "http://localhost:3005/api/custom-sites/https%3A%2F%2Fexample.com"
```

---

## Performance Considerations

1. **Embedding Calculation**: ~100-200ms per query
2. **Exa API Call**: ~1-2 seconds per language
3. **Database Operations**: <10ms
4. **Total Search Time**: ~3-7 seconds for 3 languages

**Optimization Tips:**
- Cache frequent queries
- Use connection pooling
- Implement request batching
- Consider async processing for OCR

---

## Security Notes

⚠️ **Current Implementation:**
- No authentication
- No rate limiting
- No input validation (basic)

**Production Recommendations:**
- Add API key authentication
- Implement rate limiting
- Validate all inputs
- Use HTTPS
- Add CORS restrictions
- Implement logging/monitoring
- Add request signing

---

## Version History

- **v1.0.0** (2026-04-08): Initial release
  - Multi-language search
  - Embedding-based filtering
  - OCR support
  - Custom site database
  - Vue 3 frontend

---

## Support

For issues or questions:
1. Check logs: `backend/app.py` output
2. Verify `.env` configuration
3. Check Exa API status
4. Review error messages in response

---

**Last Updated**: 2026-04-08  
**API Version**: 1.0.0
