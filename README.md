# NewsSnap AI

AI-powered news aggregation platform that delivers personalized, crisp news snaps in 5 Indian languages through an Instagram-like swipe experience.

## What It Does

- **AI News Writers** -- Agents scrape 50+ Indian news sources every 10 minutes
- **Smart Deduplication** -- Same event from multiple sources? Grouped into one story
- **60-Second Summaries** -- LLM compresses articles into crisp 60-80 word paragraphs
- **5 Languages** -- English, Hindi, Tamil, Telugu, Kannada
- **Visual Snaps** -- Clean white-background cards with image + summary + source
- **Netflix-Style Recommendations** -- Personalized feed based on your reading behavior
- **Instagram-Like UX** -- Vertical swipe, search, like, comment, share, bookmark

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + WebSocket |
| Agents | LangGraph + Groq LLM |
| Scraping | Playwright + BeautifulSoup + feedparser |
| Database | PostgreSQL + Redis |
| Search | Meilisearch |
| Frontend | React Native (Expo) |
| Deployment | Docker + Railway/Render |

## Quick Start

```bash
# Clone
git clone git@github.com:newton-school-ai/newssnap-ai.git
cd newssnap-ai

# Environment
cp .env.example .env
# Edit .env with your API keys

# Docker (recommended)
docker compose up -d

# Or manual setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py
uvicorn src.api.main:app --reload

# Frontend
cd frontend
npm install
npx expo start
```

## Project Structure

See `_internal/PROJECT_CONTEXT.md` for full architecture documentation.

## Contributing

See `CONTRIBUTING.md` for branch strategy, PR workflow, and coding standards.

## Development

See `DEVELOPMENT_GUIDE.md` for setup from scratch and daily workflow.

---

NST Engineering | Summer Profile Building Drive 2026
