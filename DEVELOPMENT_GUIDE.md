# Development Guide - NewsSnap AI

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- Docker and Docker Compose
- Git (SSH key configured with GitHub)
- GitHub CLI: `brew install gh && gh auth login`
- Playwright browsers: `playwright install chromium`

## Initial Setup (From Scratch)

### 1. Clone and Branch

```bash
git clone git@github.com:newton-school-ai/newssnap-ai.git
cd newssnap-ai
git checkout dev
git checkout -b feature/issue-N-your-feature dev
```

### 2. Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your keys:
- GROQ_API_KEY (get from groq.com -- free)
- GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET (from console.cloud.google.com)
- JWT_SECRET_KEY (generate: `python -c "import secrets; print(secrets.token_hex(32))"`)
- Database and Redis URLs (defaults work with Docker)

### 3. Start Services (Docker)

```bash
docker compose up -d db redis meilisearch
```

This starts PostgreSQL, Redis, and Meilisearch. Backend runs locally for development.

### 4. Python Environment

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 5. Database Setup

```bash
alembic upgrade head
python scripts/seed.py
```

### 6. Run Backend

```bash
uvicorn src.api.main:app --reload --port 8000
```

### 7. Frontend Setup

```bash
cd frontend
npm install
npx expo start
```

Scan QR with Expo Go on phone, or press `i` for iOS / `a` for Android emulator.

## Daily Workflow

### Starting Work

```bash
git checkout dev
git pull origin dev
git checkout -b feature/issue-N-name dev
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test
pytest tests/test_dedup_agent.py -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing

# Lint
ruff check src/
```

### Submitting Work

```bash
git add -A
git commit -m "feat: description of changes"
git push origin feature/issue-N-name
# Open PR on GitHub targeting dev
```

### Keeping Branch Updated

```bash
git checkout dev
git pull origin dev
git checkout feature/issue-N-name
git merge dev
# Resolve conflicts if any
```

## Docker (Full Stack)

```bash
# Build and start everything
docker compose up -d

# View logs
docker compose logs -f backend

# Stop
docker compose down

# Rebuild after changes
docker compose up -d --build backend
```

## API Testing

```bash
# Health check
curl http://localhost:8000/health

# Auth (get token via Google OAuth flow in browser)
open http://localhost:8000/auth/google

# Feed
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/feed?language=en&limit=20"

# Search
curl "http://localhost:8000/api/search?q=cricket&language=en"

# Admin
curl -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/admin/scrape-health
```

## Troubleshooting

### Database connection refused
```bash
docker compose up -d db
# Wait 5 seconds for PostgreSQL to start
alembic upgrade head
```

### Playwright browser not found
```bash
playwright install chromium
```

### Port already in use
```bash
lsof -i :8000  # Find process
kill -9 <PID>  # Kill it
```

### Meilisearch not indexing
```bash
docker compose restart meilisearch
python -c "from src.search.indexer import SearchIndexer; SearchIndexer().index_all()"
```

### Redis connection error
```bash
docker compose up -d redis
```
