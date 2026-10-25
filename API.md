# MYEXA API Documentation

## Overview

FastAPI-based search engine. Integrates with Exa API, provides multi-language search, embedding filtering, OCR, and custom site management.

**Base URL:** `http://localhost:3005`

---

## Endpoints

### 1. Search

**`POST /api/search`**

Multi-language search with optional embedding-based filtering.

**Request Body:**
```json
{
  "query": "search term",
  "languages": ["en", "de", "it"],
  "num_results": 10,
  "filter_by_relevance": true,
  "search_custom_db": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | — | Search query (required, non-blank) |
| `languages` | string[] | ["ru"] | Languages to search; one of `ru`, `en`, `de`, `it` |
| `num_results` | int | 10 | Results per language (**1–50**) |
| `filter_by_relevance` | bool | true | Apply embedding similarity filter |
| `search_custom_db` | bool | true | Include custom database results |

**Validation (HTTP 422):** blank/missing `query`, unsupported language codes,
or `num_results` outside 1–50.

**Response:**
```json
{
  "success": true,
  "query": "search term",
  "translations": {
    "original": "search term",
    "en": "search term",
    "de": "Suchbegriff",
    "it": "termine di ricerca"
  },
  "results": {
    "en": [
      {
        "url": "https://example.com",
        "title": "Example",
        "highlights": "Description text...",
        "score": 0.0,
        "language": "en",
        "embedding_score": 0.85,
        "relevance_index": 72.3
      }
    ],
    "custom_db": [
      {
        "id": 1,
        "url": "https://example.com",
        "title": "Example",
        "category": "reference",
        "tags": "guide, tutorial",
        "added_at": "2026-05-15 12:00:00",
        "match_count": 2
      }
    ]
  },
  "total_results": 30
}
```

- `embedding_score` — semantic similarity (0–1), only when `filter_by_relevance=true`
- `relevance_index` — weighted score (0–100)
- `translations` — Yandex Translate with Google Translate AJAX fallback (free, no key required)
- `custom_db` entries — sites matching at least one query word (2+ chars) in
  URL/title/tags, ranked by `match_count` (number of distinct matched words)

---

### 2. OCR

**`POST /api/ocr`**

Extract text from PDF or image files.

**Request:** `multipart/form-data`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `file` | file | — | PDF or image (required, max 50MB) |
| `language` | string | "eng" | Tesseract language code |

**Supported formats:** `.pdf`, `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`

**Limits:** actual body size enforced at 50MB (not just the declared
Content-Length header); PDFs over 50 pages are rejected before rendering.

**Response:**
```json
{
  "text": "Extracted text...",
  "confidence": 0.95,
  "method": "PyPDF2",
  "success": true
}
```

- `method`: `"PyPDF2"` | `"Tesseract"` | `"Failed"`
- Temp files are cleaned up automatically via `tempfile`

**cURL:**
```bash
curl -X POST http://localhost:3005/api/ocr \
  -F "file=@document.pdf" \
  -F "language=eng"
```

**Status:** `200` OK · `400` Invalid file type, malformed/oversized upload · `500` Error (generic message)

---

### 3. Custom Sites — List

**`GET /api/custom-sites`**

Returns all saved sites.

**Response:**
```json
{
  "success": true,
  "sites": [
    {
      "id": 1,
      "url": "https://example.com",
      "title": "Example",
      "category": "reference",
      "tags": "guide, tutorial",
      "added_at": "2026-05-15 12:00:00"
    }
  ],
  "count": 1
}
```

**Status:** `200` OK · `500` Server error

---

### 4. Custom Sites — Add

**`POST /api/custom-sites/add`**

Add a new site. Accepts **JSON body** (not query params).

```json
{
  "url": "https://example.com",
  "title": "Example",
  "category": "reference",
  "tags": "guide, tutorial"
}
```

| Field | Type | Required |
|-------|------|----------|
| `url` | string | yes |
| `title` | string | yes |
| `category` | string | no |
| `tags` | string | no |

**Response:**
```json
{
  "success": true,
  "message": "Site added"
}
```

**cURL:**
```bash
curl -X POST http://localhost:3005/api/custom-sites/add \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","title":"Example"}'
```

**Status:** `200` OK · `500` Server error

---

### 5. Custom Sites — Delete

**`DELETE /api/custom-sites/{id}`**

Deletes a site by its **numeric ID** (not URL).

| Param | Type | Description |
|-------|------|-------------|
| `id` | int | Site ID (from GET /api/custom-sites) |

**Response:**
```json
{
  "success": true,
  "message": "Site deleted"
}
```

**cURL:**
```bash
curl -X DELETE http://localhost:3005/api/custom-sites/1
```

**Status:** `200` OK (with `success: false` when the ID doesn't exist) · `500` Server error

---

### 6. Health Check

**`GET /api/health`**

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "port": 3005
}
```

**Status:** `200` OK

---

## Error Handling

All errors return JSON:
```json
{
  "detail": "Error message"
}
```

| Code | Meaning |
|------|---------|
| 400 | Invalid input (bad file type, malformed or oversized upload) |
| 422 | Request body failed validation (search endpoint) |
| 500 | Internal server error — `detail` is always the generic `"Internal server error"`; the real cause is logged server-side only |

---

## Examples

### Python

```python
import requests

# Search
r = requests.post("http://localhost:3005/api/search", json={
    "query": "artificial intelligence",
    "languages": ["en", "de"],
    "num_results": 5
})
data = r.json()

# Add site
r = requests.post("http://localhost:3005/api/custom-sites/add", json={
    "url": "https://example.com",
    "title": "Example"
})

# Delete site by ID
r = requests.delete("http://localhost:3005/api/custom-sites/1")

# OCR
with open("doc.pdf", "rb") as f:
    r = requests.post("http://localhost:3005/api/ocr", files={"file": f})
```

### JavaScript

```javascript
// Search
const res = await fetch('/api/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'AI', languages: ['en'] })
});
const data = await res.json();

// Get sites
const sites = await fetch('/api/custom-sites').then(r => r.json());

// Add site
await fetch('/api/custom-sites/add', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: 'https://x.com', title: 'X' })
});

// Delete site
await fetch('/api/custom-sites/1', { method: 'DELETE' });
```

### cURL

```bash
# Search
curl -X POST http://localhost:3005/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"AI","languages":["en"]}'

# List sites
curl http://localhost:3005/api/custom-sites

# Add site
curl -X POST http://localhost:3005/api/custom-sites/add \
  -H "Content-Type: application/json" \
  -d '{"url":"https://x.com","title":"X"}'

# Delete site (by ID)
curl -X DELETE http://localhost:3005/api/custom-sites/1
```

## Performance

| Operation | Time |
|-----------|------|
| Embedding calculation | ~100-200ms |
| Exa API call (per language) | ~1-2s |
| Database query | <10ms |
| Total search (3 languages) | ~3-7s |
| OCR (small image) | ~0.5-2s |

## Version

**1.1.0** — Last updated: 2026-10-25
