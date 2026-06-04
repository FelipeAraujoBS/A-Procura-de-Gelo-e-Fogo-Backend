# A Procura de Gelo e Fogo — API

**Full-text search engine** for *A Song of Ice and Fire*. Indexes 10 books, 2,400+ chapters, and tens of thousands of paragraphs from EPUB files, delivering term search, exact phrases, and proximity operators with millisecond responses.

> ⚔️ Designed for performance, zero-copy scalability, and a fluid reading experience.

Serves as the **backend API** for the **A Procura de Gelo e Fogo** ecosystem — including a [RAG microservice](https://github.com/FelipeAraujoBS/search) for LLM-powered question answering and a [Next.js frontend](https://github.com/FelipeAraujoBS/search).

---

## Table of Contents

- [Architecture](#architecture)
- [Data Pipeline](#data-pipeline)
- [Search Engine](#search-engine)
- [Chat Proxy (RAG)](#chat-proxy-rag)
- [REST API](#rest-api)
- [Security](#security)
- [Stack & Technical Decisions](#stack--technical-decisions)
- [CI/CD & Deploy](#cicd--deploy)
- [Environment Variables](#environment-variables)
- [Tests](#tests)

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│                    Client                         │
│         (Next.js / cURL / mobile)                │
└──────────────────┬───────────────────────────────┘
                   │ HTTPS
                   ▼
┌──────────────────────────────────────────────────┐
│              Fastify Server (API)                 │
│  ┌─────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ Helmet  │ │  CORS    │ │  Rate Limit       │   │
│  │ (CSP)   │ │ (origins)│ │  (60/30 req/min)  │   │
│  └─────────┘ └──────────┘ └──────────────────┘   │
│  ┌─────────┐ ┌──────────┐ ┌────────────┐ ┌──────┐│
│  │ Search  │ │  Books   │ │Chapters/POV│ │ Chat ││
│  │ Route   │ │  Route   │ │  Routes    │ │Proxy ││
│  └────┬────┘ └────┬─────┘ └──────┬─────┘ └──┬───┘│
│       │           │              │           │     │
│       ▼           ▼              ▼           │     │
│  ┌────────────────────────────────────────┐   │     │
│  │         SQLite FTS5 (read-only)        │   │     │
│  │  paragraphs (FTS5 virtual table)       │   │     │
│  │  Tokenizer: unicode61                  │   │     │
│  └────────────────────────────────────────┘   │     │
└───────────────────────────────────────────────┼─────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────────┐
                     │    RAG Microservice (FastAPI)        │
                     │    Hybrid Search + Groq LLM          │
                     └──────────────────────────────────────┘
```

### Principles

| Principle | Application |
|-----------|-------------|
| **Read-only** | Database opened in `readonly` mode — zero lock contention |
| **Stateless** | No session state, scales horizontally |
| **Defense in depth** | Helmet + CORS + Rate limit layered |
| **Zero-copy search** | FTS5 operates directly on index, no data loaded into memory |
| **Fail-fast** | Parameter validation at the start of each request |

---

## Data Pipeline

The system is more than an API — it's a **book processing platform**:

```
EPUB ──▶ HTML Extraction ──▶ Parsing (BeautifulSoup) ──▶ POV Detection ──▶ FTS5 Index
         │                      │                             │
         ▼                      ▼                             ▼
    toc.ncx                 Remove: cover,                Normalization of
    navigation              copyright, toc,               aliases (e.g. "Fedor"
                            appendices, etc.              → "Theon")
```

### Parser Highlights (`scripts/parse_epubs.py`)

- **Automatic POV detection**: analyzes the first paragraph of each HTML document in the EPUB and identifies the narrator character by capitalization heuristics + known POV list
- **Alias resolution**: maps chapter titles ("O Homem do Mercador", "Fedor") to canonical names ("Quentyn Martell", "Theon") via `pov_aliases.json`
- **Theon/Daenerys split**: automatic detection of Theon chapters that turn into Daenerys chapters mid-text (ADWD)
- **Roman numeral generation**: automatic titles like "Bran I", "Catelyn II" based on chapter ordering per POV within each book
- **Migration**: `migrate_chapter_titles.py` script for applying Roman numerals to existing databases

### Database Schema

```sql
CREATE VIRTUAL TABLE paragraphs USING fts5(
    book_number,        -- 1 to 10
    book_title,         -- "A Guerra dos Tronos"
    chapter_number,     -- chapter ordinal in book
    chapter_title,      -- "Bran I", "Catelyn II", etc.
    pov,                -- "Bran", "Catelyn" (canonical name)
    paragraph_index,    -- paragraph position in chapter
    text,               -- textual content
    tokenize = 'unicode61'  -- unicode support (Portuguese)
);
```

### Book Configuration

Books are configured via `books.json`:

```json
[
  { "filename": "books/Crônicas de Gelo e Fogo 01 - A Guerra dos Tronos-George R. R. Martin.epub", "path": "./books/..." },
  ...
]
```

---

## Search Engine

### Query Pipeline

```
Input: "inverno está chegando"
         │
         ▼
   1. Sanitization (escape FTS5 special chars: + ~ ( ) : )
         │
         ▼
   2. Exact phrase detection (double quotes)
         │
         ▼
   3. For multiple terms: NEAR(terms, 12) operator
      (maximum word distance between terms)
         │
         ▼
   4. FTS5 index query with snippet()
      (6 terms of context, <mark> on match)
         │
         ▼
   5. HTML snippet sanitization (sanitize-html)
         │
         ▼
   6. Pagination (LIMIT/OFFSET, max 100)
```

### Query Examples

| Input | Behavior |
|-------|----------|
| `"Dracarys"` | Exact phrase — literal search |
| `lobos gigantes` | `NEAR(lobos gigantes, 12)` — up to 12 words apart |
| `inverno chegando` | `NEAR(inverno chegando, 12)` — both terms nearby |
| `"Valar Morghulis"` | Exact phrase — both terms together |

### Filters

- **`book`**: filter by specific book (`WHERE book_number = ?`)
- **`povs`**: filter by multiple characters (`WHERE pov IN (...)`), comma-separated
- Both use **bind parameters** (no string concatenation) — no SQL injection

### Pagination

```json
{
  "total": 142,
  "limit": 20,
  "offset": 0,
  "results": [...]
}
```

Two queries per request: `COUNT(*)` for total + paginated `SELECT` with `LIMIT/OFFSET`.

---

## Chat Proxy (RAG)

The backend acts as a **secure proxy** to the RAG microservice:

```
POST /api/chat
  → validates message (≥ 2 chars)
  → forwards { question } to RAG_MICROSERVICE_URL/api/chat
  → returns { reply: { content, sources, timestamp } }
```

- 300s timeout with AbortController
- Graceful fallback if RAG microservice is unavailable
- Rate limited at 60 req/min

### Chat Response

```json
{
  "reply": {
    "id": "chat_1717000000000",
    "role": "assistant",
    "content": "Jaime Lannister.",
    "sources": [
      {
        "book_title": "A Tormenta de Espadas",
        "chapter_title": "Jaime VIII",
        "pov": "Jaime Lannister"
      }
    ],
    "timestamp": 1717000000000
  }
}
```

---

## REST API

### Endpoints

| Method | Route | Description | Rate Limit |
|--------|-------|-------------|------------|
| `GET` | `/health` | Health check (status, timestamp, env) | — |
| `GET` | `/search?q=&book=&povs=&limit=&offset=` | Full-text search | 30 req/min |
| `GET` | `/books` | List books with counts | 60 req/min |
| `GET` | `/books/:id` | Book details | 60 req/min |
| `GET` | `/books/:id/chapters` | Book chapters | 60 req/min |
| `GET` | `/books/:id/chapters/:chapter` | Chapter content | 60 req/min |
| `GET` | `/context?book=&chapter=&index=` | Neighboring paragraphs (±3) | 60 req/min |
| `GET` | `/povs?book=` | Available POV characters | 60 req/min |
| `POST` | `/api/chat` | Chat via RAG microservice | 60 req/min |

### Example Response

```json
GET /search?q=Dracarys&book=3

{
  "query": "Dracarys",
  "total": 5,
  "limit": 20,
  "offset": 0,
  "results": [
    {
      "book_number": 3,
      "book_title": "A Tormenta de Espadas",
      "chapter_number": 8,
      "chapter_title": "Daenerys I",
      "pov": "Daenerys",
      "paragraph_index": 42,
      "snippet": "...Drogon cuspiu fogo e gritou <mark>Dracarys</mark> enquanto as chamas..."
    }
  ]
}
```

---

## Security

| Layer | Implementation |
|-------|---------------|
| **Content Security Policy** | Helmet with restrictive directives (default-src 'self') |
| **CORS** | Origin whitelist via `ALLOWED_ORIGINS`, GET + POST only |
| **Rate Limiting** | 60 req/min global, 30 req/min for `/search` |
| **Input sanitization** | `sanitize-html` on returned snippets |
| **SQL Injection** | All parameters via bind (prepared statements) |
| **Query sanitization** | FTS5 special character escaping |

---

## Stack & Technical Decisions

### Why Fastify?

- **Performance**: 2x-3x faster than Express in benchmarks
- **Schema-based**: parameter validation with JSON Schema
- **Plugin system**: modular per route, easy to test
- **Native logger**: Pino (structured JSON in production)

### Why SQLite FTS5?

- **Zero operations**: no database server, no dependent Docker
- **Native full-text**: FTS5 is SQLite's most mature text search engine
- **Snippets**: native `snippet()` function with term highlighting
- **Portability**: single file database — versionable, copyable, deployable
- **Read-only**: no locks, no concurrency, no corruption chance in production

### Architecture Decisions

| Decision | Alternative | Why chosen |
|----------|-------------|------------|
| Single database | Elasticsearch / Meilisearch | Data fits in 50MB. A search server is overkill. |
| Read-only | Read-write | API is pure query. Read-only eliminates locks and corruption. |
| Offset pagination | Cursor / search_after | Small dataset (< 100k rows), offset is simple and sufficient. |
| Per-route rate limit | Global rate limit | `/search` is more intensive (FTS5), deserves a lower limit. |

### Error Handling

```json
{
  "error": "Parameter \"q\" must be at least 2 characters.",
  "statusCode": 400
}
```

- Validation errors: 400
- Rate limit exceeded: 429 with Portuguese message
- Internal errors: 500 (logged via Pino)

---

## CI/CD & Deploy

### GitHub Actions

```yaml
- Create test database with synthetic data
- Run 29+ tests (vitest)
- Build TypeScript
- Strict separation: CI doesn't need a real database
```

### Deploy (Render)

1. Push to `main` → CI runs tests
2. Render detects change, builds Docker image
3. `database.db` versioned in repository (not gitignored)
4. Persistent volume for database in production

### Docker Compose (dev + prod)

```yaml
services:
  backend:
    build: ./A-Procura-de-Gelo-e-Fogo-Backend
    ports: ["5000:5000"]
    volumes: ["./A-Procura-de-Gelo-e-Fogo-Backend/database.db:/app/database.db"]
    environment:
      - ALLOWED_ORIGINS=http://localhost:3000
      - RAG_MICROSERVICE_URL=http://rag:7860
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:5000/health"]
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PORT` | No | 3000 | Server port |
| `ALLOWED_ORIGINS` | Yes (prod) | — | CORS allowed origins (comma-separated) |
| `NODE_ENV` | No | development | `production` enables structured JSON logs |
| `DB_PATH` | No | ./database.db | SQLite database path |
| `RAG_MICROSERVICE_URL` | No | — | RAG microservice URL (e.g. http://rag:7860) |

---

## Tests

```bash
npm test           # 29+ tests
npm run test:watch # Watch mode
```

Tests use `vitest` + `supertest` with an isolated synthetic database. They validate:

- Single and multi-term search
- Exact phrase search
- Book and POV filters
- Pagination
- Rate limiting
- Health check
- Parameter validation

---

> Designed and developed by [FelipeAraujoBS](https://github.com/FelipeAraujoBS)
