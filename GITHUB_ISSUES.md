# NewsSnap AI - GitHub Issues

All 33 issues in detailed format for GitHub creation via `bash scripts/create_github_issues.sh`.

---

## M1: Project Scaffold, DB, and Auth

---

### Issue 1 - Initialize repo scaffold, CI workflow, Docker setup

**Why:**
Every production project needs a clean foundation: consistent directory structure, automated CI to catch bugs early, and Docker for reproducible environments. Without this, contributors waste time on setup instead of building features.

**What to build:**
- Complete directory structure matching the file structure in PROJECT_CONTEXT.md
- GitHub Actions CI workflow: lint (flake8/ruff) + test (pytest) on every PR to dev
- Dockerfile for backend (Python 3.11, FastAPI)
- docker-compose.yml with backend, PostgreSQL, Redis, Meilisearch services
- Pre-commit hooks for linting

**Files to create/update:**
- .github/workflows/ci.yml
- Dockerfile
- docker-compose.yml
- src/__init__.py and all sub-package __init__.py files
- pyproject.toml or setup.cfg for linting config
- All directory stubs with .gitkeep files

**How to test locally:**
```bash
# Lint passes
ruff check src/
# Tests pass (empty test suite initially)
pytest tests/ -v
# Docker builds
docker compose build
docker compose up -d
docker compose ps  # all services healthy
# CI runs on push
git push origin feature/issue-1-scaffold
```

**Acceptance Criteria:**
- [ ] Directory structure matches PROJECT_CONTEXT.md file structure
- [ ] `ruff check src/` passes with zero errors
- [ ] `pytest tests/` runs and passes (at least 1 placeholder test)
- [ ] `docker compose up -d` starts backend, PostgreSQL, Redis, Meilisearch
- [ ] GitHub Actions CI triggers on PR to dev and passes
- [ ] Pre-commit hook runs linter before each commit
- [ ] README.md has project overview and quick start instructions

**Branch:** `feature/issue-1-scaffold`
**Dependencies:** None (first issue)

---

### Issue 2 - Design database schema, Alembic migrations, and seed data

**Why:**
The entire application depends on a well-designed database. Articles, snaps, users, interactions, recommendations -- all need proper tables with indexes for fast queries. Getting the schema right early prevents painful migrations later.

**What to build:**
- SQLAlchemy models for all entities: User, Article, Snap, Story, Source, Category, Interaction, Comment, Notification, UserPreference
- Alembic migration setup with initial migration
- Seed data script: sample sources, categories, test user
- Database indexes for common queries (feed by language, articles by publish_time, interactions by user)

**Files to create/update:**
- src/models/user.py (User, UserPreference)
- src/models/article.py (Article, ArticleEmbedding)
- src/models/snap.py (Snap, SnapTranslation)
- src/models/story.py (Story, StoryArticle)
- src/models/source.py (Source)
- src/models/category.py (Category)
- src/models/interaction.py (Interaction, Comment)
- src/models/notification.py (Notification)
- src/models/base.py (Base, common mixins)
- src/models/__init__.py (import all models)
- alembic.ini
- alembic/env.py
- alembic/versions/001_initial_schema.py
- scripts/seed.py

**How to test locally:**
```bash
# Start PostgreSQL
docker compose up -d db
# Run migrations
alembic upgrade head
# Verify tables created
python -c "from src.models import *; print('All models imported successfully')"
# Run seed
python scripts/seed.py
# Verify seed data
python -c "
from sqlalchemy import create_engine, text
engine = create_engine('postgresql://newssnap:newssnap@localhost:5432/newssnap')
with engine.connect() as conn:
    result = conn.execute(text('SELECT count(*) FROM sources'))
    print(f'Sources: {result.scalar()}')
    result = conn.execute(text('SELECT count(*) FROM categories'))
    print(f'Categories: {result.scalar()}')
"
```

**Acceptance Criteria:**
- [ ] All 10 SQLAlchemy models defined with proper relationships and constraints
- [ ] `alembic upgrade head` creates all tables without errors
- [ ] `alembic downgrade base` drops all tables cleanly
- [ ] Indexes exist on: articles.publish_time, articles.language, articles.source_id, interactions.user_id, interactions.article_id, snaps.article_id, snaps.language
- [ ] Seed script creates: 20+ sources across 5 languages, 19 categories, 1 test user
- [ ] Foreign keys enforce referential integrity (delete article cascades to snaps, interactions, comments)
- [ ] All models have created_at and updated_at timestamps

**Branch:** `feature/issue-2-db-schema`
**Dependencies:** Issue 1

---

### Issue 3 - Build news source configuration and registry system

**Why:**
The scraper needs to know HOW to scrape each news source -- what selectors to use, what URL patterns to follow, what language the source publishes in. A registry system makes it easy to add new sources without changing code.

**What to build:**
- Source configuration schema (JSON format) defining: base_url, article_list_url, article_link_selector, title_selector, body_selector, image_selector, category_mapping, language, scrape_type (playwright/rss/static), rate_limit_seconds
- Source registry that loads configs from JSON files and database
- Source health tracker (last_scrape_time, success_count, error_count, is_healthy)
- API endpoints to list sources, check health, add/update source configs
- Initial configs for 10+ sources (mix of English and Hindi)

**Files to create/update:**
- src/scrapers/source_registry.py
- src/scrapers/source_configs/ndtv.json
- src/scrapers/source_configs/timesofindia.json
- src/scrapers/source_configs/hindustantimes.json
- src/scrapers/source_configs/indianexpress.json
- src/scrapers/source_configs/aajtak.json
- src/scrapers/source_configs/dainikbhaskar.json
- src/scrapers/source_configs/thehindu.json (RSS)
- src/scrapers/source_configs/mint.json
- src/scrapers/source_configs/news18.json
- src/scrapers/source_configs/zeenews_hindi.json
- src/api/sources.py
- tests/test_source_registry.py

**How to test locally:**
```bash
# Load all source configs
python -c "
from src.scrapers.source_registry import SourceRegistry
registry = SourceRegistry()
sources = registry.get_all_sources()
print(f'Loaded {len(sources)} sources')
for s in sources:
    print(f'  {s.name} ({s.language}) - {s.scrape_type}')
"
# Test API
uvicorn src.api.main:app --reload
curl http://localhost:8000/api/sources
curl http://localhost:8000/api/sources/health
# Run tests
pytest tests/test_source_registry.py -v
```

**Acceptance Criteria:**
- [ ] Source config JSON schema is documented and validated on load
- [ ] At least 10 source configs created (mix of Playwright, RSS, static)
- [ ] SourceRegistry loads from both JSON files and database
- [ ] Source health tracking records last_scrape_time, success_count, error_count
- [ ] API endpoint GET /api/sources returns all sources with health status
- [ ] Invalid source configs are rejected with clear error messages
- [ ] Adding a new source requires only creating a JSON config file (no code changes)

**Branch:** `feature/issue-3-source-config`
**Dependencies:** Issue 2

---

### Issue 4 - Build user auth API with Google OAuth and JWT

**Why:**
Every user needs an account to get personalized recommendations, save preferences, and interact with content. Google OAuth is the standard for NST projects -- every Indian user has a Google account, zero friction signup.

**What to build:**
- Google OAuth 2.0 flow: frontend redirects to Google consent -> backend exchanges auth code for profile -> creates user if new -> issues JWT
- JWT tokens: 24-hour access token + 7-day refresh token
- User onboarding: first login prompts language selection (1 primary + optional secondary) and category preferences (select 3+ from list)
- Protected route middleware (require valid JWT)
- User profile API (get/update profile, preferences, language)

**Files to create/update:**
- src/api/auth.py (Google OAuth endpoints: /auth/google, /auth/google/callback, /auth/refresh)
- src/api/users.py (profile, preferences, onboarding)
- src/api/middleware.py (JWT validation middleware)
- src/config/settings.py (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, JWT_SECRET_KEY, JWT configs)
- src/utils/auth_utils.py (create_token, verify_token, get_google_profile)
- tests/test_auth.py

**How to test locally:**
```bash
# Set up Google OAuth (console.cloud.google.com)
# Add to .env: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, JWT_SECRET_KEY
# Start server
uvicorn src.api.main:app --reload
# Test OAuth flow (browser)
open http://localhost:8000/auth/google
# After callback, verify JWT returned
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/users/me
# Test refresh
curl -X POST http://localhost:8000/auth/refresh -d '{"refresh_token": "<token>"}'
# Test onboarding
curl -X POST -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/users/onboarding \
  -d '{"primary_language": "hi", "categories": ["politics", "sports", "technology"]}'
# Run tests
pytest tests/test_auth.py -v
```

**Acceptance Criteria:**
- [ ] Google OAuth flow works end-to-end (redirect -> consent -> callback -> JWT)
- [ ] JWT access token expires in 24 hours, refresh token in 7 days
- [ ] Protected routes return 401 without valid JWT
- [ ] First-time users are flagged as needing onboarding (is_onboarded=false)
- [ ] Onboarding saves language preference and 3+ category selections
- [ ] GET /api/users/me returns user profile with preferences
- [ ] Token refresh endpoint issues new access token with valid refresh token
- [ ] Invalid/expired tokens are rejected with appropriate error messages

**Branch:** `feature/issue-4-google-oauth`
**Dependencies:** Issue 2

---

## M2: News Scraping Pipeline

---

### Issue 5 - Build Playwright-based web scraper for JS-rendered news sites

**Why:**
Most major Indian news websites (NDTV, Times of India, Aaj Tak) are built with React/Next.js and require JavaScript execution to render article content. A simple HTTP request only gets an empty shell. Playwright renders the full page like a real browser.

**What to build:**
- Playwright scraper that navigates to source article list pages, extracts article links, then visits each link to extract full content
- Configurable via source config JSON (selectors, rate limits, pagination)
- Rate limiting: configurable delay between requests (default 2s per domain)
- Rotating user agents to avoid blocks
- Error handling: retry 3x with exponential backoff, log failures
- Headless browser pool management (reuse browser instances)

**Files to create/update:**
- src/scrapers/playwright_scraper.py
- src/scrapers/browser_pool.py
- src/utils/text_utils.py (clean HTML, extract text, normalize whitespace)
- tests/test_playwright_scraper.py

**How to test locally:**
```bash
# Install Playwright browsers
playwright install chromium
# Test scraping a single source
python -c "
import asyncio
from src.scrapers.playwright_scraper import PlaywrightScraper
async def test():
    scraper = PlaywrightScraper()
    articles = await scraper.scrape_source('ndtv')
    print(f'Scraped {len(articles)} articles from NDTV')
    for a in articles[:3]:
        print(f'  Title: {a.title[:80]}')
        print(f'  Body: {len(a.body)} chars')
        print(f'  Image: {a.image_url}')
asyncio.run(test())
"
# Run tests
pytest tests/test_playwright_scraper.py -v
```

**Acceptance Criteria:**
- [ ] Scraper successfully extracts articles from at least 5 JS-rendered news sites
- [ ] Each article has: title, body (full text), image_url, source_url, publish_time, category
- [ ] Rate limiting enforced (configurable delay between requests per domain)
- [ ] Rotating user agents (at least 10 different agents)
- [ ] Failed requests retry 3x with exponential backoff (1s, 2s, 4s)
- [ ] Browser pool reuses Playwright instances (does not spawn new browser per request)
- [ ] Scrape errors are logged with source name, URL, and error details
- [ ] Scraper respects robots.txt directives

**Branch:** `feature/issue-5-playwright-scraper`
**Dependencies:** Issue 3

---

### Issue 6 - Build RSS and API scraper for feed-based news sources

**Why:**
Some news sites offer RSS/Atom feeds (The Hindu, Business Standard) which are faster and lighter to scrape than full page rendering. RSS feeds provide structured data (title, summary, link, publish date) without needing Playwright overhead.

**What to build:**
- RSS/Atom feed parser using feedparser library
- Support for full-content feeds (summary contains full article) and link-only feeds (need to follow link for body)
- For link-only feeds: use httpx + BeautifulSoup to fetch article body
- Normalize feed entries to same Article schema as Playwright scraper
- Handle feed-specific quirks: encoding issues, missing fields, date format variations

**Files to create/update:**
- src/scrapers/rss_scraper.py
- src/scrapers/static_scraper.py (httpx + BeautifulSoup for static pages)
- tests/test_rss_scraper.py

**How to test locally:**
```bash
# Test RSS scraping
python -c "
import asyncio
from src.scrapers.rss_scraper import RSSScraper
async def test():
    scraper = RSSScraper()
    articles = await scraper.scrape_source('thehindu')
    print(f'Scraped {len(articles)} articles from The Hindu RSS')
    for a in articles[:3]:
        print(f'  Title: {a.title[:80]}')
        print(f'  Published: {a.publish_time}')
asyncio.run(test())
"
# Run tests
pytest tests/test_rss_scraper.py -v
```

**Acceptance Criteria:**
- [ ] RSS scraper parses Atom and RSS 2.0 feeds correctly
- [ ] Full-content feeds: article body extracted from feed entry
- [ ] Link-only feeds: article body fetched via httpx + BeautifulSoup
- [ ] Normalized output matches same Article schema as Playwright scraper
- [ ] Date parsing handles multiple formats (ISO 8601, RFC 822, custom)
- [ ] Encoding issues handled (UTF-8, ISO-8859-1, etc.)
- [ ] At least 3 RSS-based sources tested and working

**Branch:** `feature/issue-6-rss-scraper`
**Dependencies:** Issue 3

---

### Issue 7 - Build article parser and content normalizer

**Why:**
Raw scraped content is messy -- HTML tags, ads, navigation text, related article links all mixed with actual content. The parser must extract clean, structured article data regardless of source format.

**What to build:**
- Article parser using newspaper3k + custom extraction rules
- Content normalizer: strip HTML, remove ads/navigation, extract clean body text
- Image extractor: find lead image from og:image, first large image, or article thumbnail
- Category detector: map article to standardized categories based on source URL patterns and content keywords
- Language detector: verify article language matches source config
- Metadata extractor: author, publish_time, tags

**Files to create/update:**
- src/scrapers/article_parser.py
- src/utils/text_utils.py (add HTML cleaning, ad removal, text normalization)
- src/utils/image_utils.py (image URL validation, og:image extraction)
- src/config/settings.py (add category mapping, language codes)
- tests/test_article_parser.py

**How to test locally:**
```bash
# Test article parsing
python -c "
from src.scrapers.article_parser import ArticleParser
parser = ArticleParser()
# Test with a real article URL
result = parser.parse('https://www.ndtv.com/india-news/some-article')
print(f'Title: {result.title}')
print(f'Body: {result.body[:200]}...')
print(f'Image: {result.image_url}')
print(f'Category: {result.category}')
print(f'Language: {result.language}')
print(f'Author: {result.author}')
print(f'Published: {result.publish_time}')
"
# Run tests
pytest tests/test_article_parser.py -v
```

**Acceptance Criteria:**
- [ ] Parser extracts clean body text with no HTML tags, ads, or navigation
- [ ] Lead image extracted from og:image meta tag with fallback to first large image
- [ ] Category assigned from URL patterns and content keywords (all 19 categories)
- [ ] Language detection verifies article matches expected source language
- [ ] Author and publish_time extracted when available
- [ ] Articles with body < 100 words are flagged as incomplete
- [ ] Parser works on articles from all configured sources

**Branch:** `feature/issue-7-article-parser`
**Dependencies:** Issues 5, 6

---

### Issue 8 - Build scrape scheduler with monitoring and error handling

**Why:**
The scrape pipeline must run automatically every 10 minutes, rotating through sources, handling failures gracefully, and providing visibility into pipeline health. Without scheduling and monitoring, the app has no fresh content.

**What to build:**
- APScheduler-based scrape scheduler running every 10 minutes
- Source rotation: spread sources across the 10-minute window (not all at once)
- Pipeline orchestration: scrape -> parse -> store in database
- Error handling: mark source unhealthy after 5 consecutive failures, auto-retry after cooldown
- Health monitoring API: last scrape time per source, success/error counts, pipeline throughput
- Scrape status dashboard data (articles scraped per hour, per source, error rates)

**Files to create/update:**
- src/scheduler/jobs.py
- src/scheduler/scrape_pipeline.py
- src/api/admin.py (health monitoring endpoints)
- tests/test_scheduler.py

**How to test locally:**
```bash
# Start scheduler
python -c "
from src.scheduler.jobs import start_scheduler
start_scheduler()  # runs in foreground, scrapes every 10 min
"
# Check health
curl http://localhost:8000/api/admin/scrape-health
# Check recent articles
curl http://localhost:8000/api/admin/recent-articles?limit=10
# Run tests
pytest tests/test_scheduler.py -v
```

**Acceptance Criteria:**
- [ ] Scheduler triggers scrape pipeline every 10 minutes
- [ ] Sources are spread across the interval (not all scraped simultaneously)
- [ ] Scraped articles are stored in database with all required fields
- [ ] Source marked unhealthy after 5 consecutive scrape failures
- [ ] Unhealthy sources are retried after 30-minute cooldown
- [ ] GET /api/admin/scrape-health returns per-source health metrics
- [ ] Pipeline logs: articles scraped, duplicates found, errors per cycle
- [ ] Scheduler survives individual source failures (does not crash entire cycle)

**Branch:** `feature/issue-8-scrape-scheduler`
**Dependencies:** Issues 5, 6, 7

---

## M3: AI Content Pipeline

---

### Issue 9 - Build embedding-based deduplication agent

**Why:**
Multiple sources report the same news events. Without deduplication, users see 5 versions of the same cricket score or election result. The dedup agent uses semantic similarity (not exact match) to catch paraphrased duplicates.

**What to build:**
- Embedding generator using sentence-transformers (all-MiniLM-L6-v2)
- Dedup agent that compares new article embeddings against last 48 hours of articles
- Cosine similarity threshold: > 0.85 = duplicate (configurable)
- Duplicate handling: keep article from highest-priority source, link others as "also reported by"
- Store embeddings in database for efficient comparison
- Batch processing for incoming articles

**Files to create/update:**
- src/agents/dedup_agent.py
- src/models/article.py (add embedding column or separate ArticleEmbedding table)
- alembic/versions/002_add_embeddings.py
- tests/test_dedup_agent.py

**How to test locally:**
```bash
# Test dedup
python -c "
from src.agents.dedup_agent import DedupAgent
agent = DedupAgent()
# Two articles about same event
article1 = {'title': 'India wins cricket match against Australia', 'body': 'India defeated Australia by 5 wickets...'}
article2 = {'title': 'India beats Australia in thrilling cricket match', 'body': 'In a thrilling encounter, India beat Australia...'}
article3 = {'title': 'Stock market hits record high', 'body': 'Sensex crossed 80000 mark...'}
result = agent.check_duplicates([article1, article2, article3])
print(f'Duplicates found: {result.duplicates}')
print(f'Unique articles: {result.unique}')
"
# Run tests
pytest tests/test_dedup_agent.py -v
```

**Acceptance Criteria:**
- [ ] Embeddings generated using sentence-transformers (all-MiniLM-L6-v2)
- [ ] Cosine similarity > 0.85 correctly identifies paraphrased duplicates
- [ ] Unique articles (similarity < 0.85) pass through
- [ ] Duplicate articles linked to primary via "also_reported_by" field
- [ ] Primary article selected from highest-priority source
- [ ] Comparison window is configurable (default 48 hours)
- [ ] Batch processing handles 100+ articles per cycle efficiently (< 5 seconds)
- [ ] Embeddings stored in database for reuse

**Branch:** `feature/issue-9-dedup-agent`
**Dependencies:** Issue 8

---

### Issue 10 - Build story clustering agent for related articles

**Why:**
Beyond exact duplicates, multiple unique articles often cover the same "story" from different angles. Clustering these into stories prevents feed repetition and lets users see "5 sources reported this" instead of 5 separate snaps.

**What to build:**
- Story clustering using DBSCAN on article embeddings
- Cluster parameters: eps=0.3, min_samples=2 (configurable)
- Each cluster becomes a "Story" with a primary article and related articles
- Primary article selection: highest quality score (length, source priority, image quality)
- Story merging: new articles can be added to existing stories
- Story API: get story with all related articles

**Files to create/update:**
- src/agents/story_clusterer.py
- src/api/stories.py
- tests/test_story_clusterer.py

**How to test locally:**
```bash
# Test clustering
python -c "
from src.agents.story_clusterer import StoryClusterer
clusterer = StoryClusterer()
# Feed articles from last scrape cycle
stories = clusterer.cluster_recent_articles(hours=6)
print(f'Found {len(stories)} stories')
for s in stories:
    print(f'  Story: {s.primary_article.title[:60]}')
    print(f'  Related: {len(s.related_articles)} articles')
"
# Run tests
pytest tests/test_story_clusterer.py -v
```

**Acceptance Criteria:**
- [ ] DBSCAN clustering groups related articles into stories
- [ ] Each story has exactly one primary article and 0+ related articles
- [ ] Primary article is selected by quality score (source priority, content length, has image)
- [ ] New articles are checked against existing stories before creating new ones
- [ ] Singleton articles (no cluster) become standalone stories
- [ ] GET /api/stories/{id} returns story with all related articles
- [ ] Clustering runs in < 10 seconds for 500 articles

**Branch:** `feature/issue-10-story-clustering`
**Dependencies:** Issue 9

---

### Issue 11 - Build LLM summarizer agent for crisp 1-paragraph summaries

**Why:**
This is the core value proposition. Users want news in 60 seconds, not 6-minute articles. The summarizer compresses a 500-2000 word article into a crisp 60-80 word paragraph that preserves key facts and is engaging to read.

**What to build:**
- LangGraph-based summarizer agent using Groq LLM
- Prompt engineering: factual, engaging, no clickbait, preserves who/what/when/where/why
- Category-aware summarization (finance = data-heavy, sports = score-focused, politics = quote-focused)
- Quality validation: reject summaries that are too short (< 40 words), too long (> 100 words), or miss key entities
- Retry logic: if quality check fails, re-summarize with more specific prompt
- Batch summarization for efficiency

**Files to create/update:**
- src/agents/summarizer_agent.py
- src/agents/supervisor.py (pipeline orchestration)
- src/config/settings.py (add Groq API config, summary length limits)
- tests/test_summarizer_agent.py

**How to test locally:**
```bash
# Test summarization
python -c "
from src.agents.summarizer_agent import SummarizerAgent
agent = SummarizerAgent()
article_body = '''<paste a 500+ word news article here>'''
summary = agent.summarize(article_body, category='politics')
print(f'Summary ({len(summary.split())} words):')
print(summary)
"
# Test batch
python -c "
from src.agents.summarizer_agent import SummarizerAgent
agent = SummarizerAgent()
articles = [...]  # list of article bodies
summaries = agent.batch_summarize(articles)
for s in summaries:
    print(f'{len(s.split())} words: {s[:80]}...')
"
# Run tests
pytest tests/test_summarizer_agent.py -v
```

**Acceptance Criteria:**
- [ ] Summaries are 60-80 words (configurable range)
- [ ] Key facts preserved: who, what, when, where, why (at least 3 of 5)
- [ ] No clickbait language in summaries (verified by quality check)
- [ ] Category-aware prompts produce different styles (finance vs sports vs politics)
- [ ] Quality check rejects and re-summarizes bad outputs (max 2 retries)
- [ ] Source attribution included in summary metadata (not in text body)
- [ ] Batch processing: 20 articles summarized in < 30 seconds via Groq
- [ ] Handles articles in English and Hindi (source language detection)

**Branch:** `feature/issue-11-summarizer-agent`
**Dependencies:** Issue 10

---

### Issue 12 - Build content quality filter to reject clickbait and spam

**Why:**
Not every scraped article deserves a snap. Clickbait, sponsored content, press releases, incomplete articles, and spam waste LLM calls and degrade user experience. Filter them before summarization.

**What to build:**
- Quality scoring system: rate articles on multiple dimensions
- Clickbait detector: compare title sensationalism against body content (LLM-based)
- Completeness check: body length > 100 words, has meaningful content (not just captions/ads)
- Sponsored content filter: detect "sponsored", "partner content", "advertorial" markers
- Duplicate press release filter: detect boilerplate PR text patterns
- Quality threshold: articles below threshold are rejected with logged reason
- Admin API: view rejected articles with rejection reasons

**Files to create/update:**
- src/agents/quality_filter.py
- src/api/admin.py (add rejected articles endpoint)
- tests/test_quality_filter.py

**How to test locally:**
```bash
# Test quality filter
python -c "
from src.agents.quality_filter import QualityFilter
qf = QualityFilter()
# Good article
good = {'title': 'RBI holds repo rate at 6.5%', 'body': '(400 word article about monetary policy...)'}
# Clickbait
bad = {'title': 'You WON'T BELIEVE what happened next!!!', 'body': '(thin article with ads...)'}
print(f'Good article score: {qf.score(good)}')  # should be > threshold
print(f'Bad article score: {qf.score(bad)}')    # should be < threshold
"
# Run tests
pytest tests/test_quality_filter.py -v
```

**Acceptance Criteria:**
- [ ] Quality score computed on: content length, title/body coherence, source reliability, completeness
- [ ] Clickbait articles rejected (sensational title, thin body)
- [ ] Articles with body < 100 words rejected as incomplete
- [ ] Sponsored content detected and filtered (keyword + pattern matching)
- [ ] Quality threshold is configurable (default: 0.4 out of 1.0)
- [ ] Rejected articles logged with: article_id, source, rejection_reason, score
- [ ] GET /api/admin/rejected-articles returns recent rejections with reasons
- [ ] Filter processes 100 articles in < 10 seconds

**Branch:** `feature/issue-12-quality-filter`
**Dependencies:** Issue 9

---

## M4: Translation and Snap Generation

---

### Issue 13 - Build multi-language translator agent for 5 Indian languages

**Why:**
India has 22 official languages and hundreds of millions who prefer consuming content in their native language. Translating summaries into Hindi, Tamil, Telugu, and Kannada (plus English) dramatically expands the user base.

**What to build:**
- LangGraph-based translator agent using Groq LLM
- Language-specific system prompts for natural (not literal) translations
- Support for: English (en), Hindi (hi), Tamil (ta), Telugu (te), Kannada (kn)
- Translation from source language to all other 4 languages
- Quality check: back-translate a sample to verify meaning preservation
- Fallback: IndicTrans2 model for offline translation when LLM quota exhausted
- Batch translation for efficiency

**Files to create/update:**
- src/agents/translator_agent.py
- src/config/settings.py (add language configs, translation prompts)
- src/utils/language_utils.py (language detection, script validation)
- tests/test_translator_agent.py

**How to test locally:**
```bash
# Test translation
python -c "
from src.agents.translator_agent import TranslatorAgent
agent = TranslatorAgent()
summary_en = 'India scored 350 runs in the first innings of the test match against England at Lords.'
translations = agent.translate_all(summary_en, source_lang='en')
for lang, text in translations.items():
    print(f'{lang}: {text}')
"
# Run tests
pytest tests/test_translator_agent.py -v
```

**Acceptance Criteria:**
- [ ] Translations produced for all 5 languages from any source language
- [ ] Translations read naturally (not word-by-word literal translation)
- [ ] Language-specific prompts handle idioms and cultural context
- [ ] Back-translation quality check passes for 90%+ of translations
- [ ] IndicTrans2 fallback works when Groq API is unavailable
- [ ] Batch translation: 20 summaries to all 5 languages in < 60 seconds
- [ ] Output text uses correct script for each language (Devanagari, Tamil, Telugu, Kannada)
- [ ] Numbers, proper nouns, and abbreviations handled correctly across languages

**Branch:** `feature/issue-13-translator-agent`
**Dependencies:** Issue 11

---

### Issue 14 - Build snap image generator with white background layout

**Why:**
News snaps are the product's visual identity. Each snap must be a clean, consistent, mobile-optimized card: white background, lead image, crisp summary text, source attribution. Think Instagram post meets news brief.

**What to build:**
- Snap image generator using Pillow
- Layout: white background, 1080x1920 (9:16 mobile), lead image at top (16:9), category badge, summary text (system font), source + timestamp at bottom
- Text rendering: auto-wrap to fit width, proper line spacing, font size auto-adjusted for text length
- Interaction bar placeholder (like/comment/share rendered in frontend, not in image)
- Generate snaps for all language versions of each article
- Store snap metadata in database, images on disk (or future CDN)

**Files to create/update:**
- src/snaps/snap_generator.py
- src/snaps/image_handler.py
- src/snaps/templates/ (template configs as JSON)
- src/utils/image_utils.py (add text rendering, image composition utilities)
- tests/test_snap_generator.py

**How to test locally:**
```bash
# Test snap generation
python -c "
from src.snaps.snap_generator import SnapGenerator
gen = SnapGenerator()
snap = gen.generate(
    title='India Wins Cricket World Cup',
    summary='India defeated Australia by 6 wickets in the final...',
    image_url='https://example.com/cricket.jpg',
    category='Sports',
    source='Times of India',
    language='en'
)
snap.save('test_snap.png')
print(f'Snap saved: {snap.size}')
"
# Run tests
pytest tests/test_snap_generator.py -v
```

**Acceptance Criteria:**
- [ ] Snap image is 1080x1920 pixels (9:16 mobile aspect ratio)
- [ ] White background (#FFFFFF) with clean typography
- [ ] Lead image displayed at top in 16:9 aspect ratio
- [ ] Category badge (colored pill) displayed below image
- [ ] Summary text auto-wraps and scales font size based on text length
- [ ] Source name and time-ago displayed at bottom
- [ ] Snap generated for each language version (text in correct script)
- [ ] Image file size < 500KB (optimized for mobile)
- [ ] Handles missing lead image (uses category placeholder)

**Branch:** `feature/issue-14-snap-generator`
**Dependencies:** Issue 13

---

### Issue 15 - Build image extraction and processing pipeline

**Why:**
News snaps need compelling images. The pipeline must reliably extract lead images from articles, validate them, resize for mobile, and provide fallbacks when no image is available.

**What to build:**
- Image extractor: try og:image meta tag, then first large image in article body, then source favicon
- Image validator: reject images that are too small (< 200x200), broken URLs, or generic site logos
- Image resizer: crop/resize to 16:9 aspect ratio for snap layout
- Image optimizer: compress to < 500KB for mobile delivery
- Category placeholder system: generic images for each category when no lead image found
- Image cache: store processed images to avoid re-downloading

**Files to create/update:**
- src/snaps/image_handler.py (expand from Issue 14)
- src/utils/image_utils.py (add validation, resize, optimize)
- frontend/assets/placeholders/ (category placeholder images)
- tests/test_image_handler.py

**How to test locally:**
```bash
# Test image extraction
python -c "
from src.snaps.image_handler import ImageHandler
handler = ImageHandler()
# Test with article URL
image = handler.extract_and_process('https://www.ndtv.com/some-article')
print(f'Image size: {image.size}')
print(f'File size: {len(image.tobytes())} bytes')
# Test placeholder fallback
placeholder = handler.get_placeholder('sports')
print(f'Placeholder: {placeholder.size}')
"
# Run tests
pytest tests/test_image_handler.py -v
```

**Acceptance Criteria:**
- [ ] Extracts lead image from og:image, first large img, or article thumbnail
- [ ] Rejects images smaller than 200x200 pixels
- [ ] Rejects broken image URLs (404, timeout > 5s)
- [ ] Resizes images to 16:9 aspect ratio (1080x608) with smart cropping
- [ ] Output images compressed to < 500KB
- [ ] Category placeholders available for all 19 categories
- [ ] Image cache prevents re-downloading same URL
- [ ] Handles JPEG, PNG, WebP input formats

**Branch:** `feature/issue-15-image-pipeline`
**Dependencies:** Issue 14

---

### Issue 16 - Build snap template system for different content categories

**Why:**
Not all news is the same. Finance news benefits from data-centric layout, sports from score-centric layout, entertainment from image-heavy layout. Different templates make snaps more engaging and scannable per category.

**What to build:**
- Template configuration system (JSON-based)
- Templates for: General (default), Finance/Business (with data highlights), Sports (with score display), Entertainment (larger image), Politics/National (with quote highlight), Technology/Science (with key stats), Crime/Defence (bold headline), Education/Jobs (info-card style)
- Template selector: auto-select based on article category (19 categories mapped to 8 template types)
- Template renderer: apply template to snap composition
- Custom colors per category (badge color, accent color for all 19 categories)

**Files to create/update:**
- src/snaps/templates/general.json
- src/snaps/templates/finance.json
- src/snaps/templates/sports.json
- src/snaps/templates/entertainment.json
- src/snaps/templates/politics.json
- src/snaps/templates/technology.json
- src/snaps/template_renderer.py
- tests/test_template_renderer.py

**How to test locally:**
```bash
# Test template rendering
python -c "
from src.snaps.template_renderer import TemplateRenderer
renderer = TemplateRenderer()
# Generate snaps with different templates
for category in ['finance', 'sports', 'entertainment', 'politics']:
    snap = renderer.render(
        category=category,
        title='Test Article',
        summary='Test summary content...',
        image_url=None,
        source='Test Source',
        language='en'
    )
    snap.save(f'test_snap_{category}.png')
    print(f'{category}: saved')
"
# Run tests
pytest tests/test_template_renderer.py -v
```

**Acceptance Criteria:**
- [ ] 8 template types covering all 19 categories (general, finance/business, sports, entertainment, politics/national, tech/science, crime/defence, education/jobs)
- [ ] Each template has unique layout and color scheme
- [ ] All 19 categories mapped to a template with unique badge color
- [ ] Finance/Business template highlights numerical data
- [ ] Sports template has score/result display area
- [ ] Crime/Defence template uses bold headline styling
- [ ] Education/Jobs template uses info-card layout
- [ ] Template auto-selected based on article category
- [ ] Templates defined as JSON configs (no hardcoded layouts)
- [ ] All templates produce valid 1080x1920 snap images
- [ ] Templates render correctly in all 5 languages

**Branch:** `feature/issue-16-snap-templates`
**Dependencies:** Issues 14, 15

---

## M5: Feed API, Search, and Interactions

---

### Issue 17 - Build personalized feed API with pagination and filtering

**Why:**
The feed is the product. Users open the app and see a personalized stream of news snaps. The API must serve the right content, fast, with proper pagination for infinite scroll.

**What to build:**
- GET /api/feed - personalized feed based on user preferences and recommendation scores
- Pagination: cursor-based (not offset) for efficient infinite scroll
- Filters: language (required), categories (optional), time range
- Default feed for new users: trending + category mix based on onboarding preferences
- Feed response: snap metadata (not full image) with CDN URLs for images
- Redis caching: pre-compute top 50 feed items per user, refresh on new content

**Files to create/update:**
- src/api/feed.py
- src/recommendation/engine.py (basic version, expanded in M6)
- tests/test_feed_api.py

**How to test locally:**
```bash
# Start server
uvicorn src.api.main:app --reload
# Get feed
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/feed?language=en&limit=20"
# Get feed with category filter
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/feed?language=hi&categories=sports,politics&limit=10"
# Test pagination
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/feed?language=en&limit=20&cursor=<cursor_from_prev>"
# Run tests
pytest tests/test_feed_api.py -v
```

**Acceptance Criteria:**
- [ ] GET /api/feed returns personalized snap list with cursor-based pagination
- [ ] Language filter is required (returns 400 without it)
- [ ] Category filter narrows results to selected categories
- [ ] New users get trending + preference-based default feed
- [ ] Each feed item includes: snap_id, article_id, title, summary, image_url, category, source, time_ago, interaction_counts
- [ ] Feed response time < 200ms for cached users
- [ ] Redis cache invalidated when new snaps are generated
- [ ] Pagination handles end-of-feed gracefully (empty next_cursor)

**Branch:** `feature/issue-17-feed-api`
**Dependencies:** Issues 4, 14

---

### Issue 18 - Build Meilisearch integration for multi-language search

**Why:**
Users need to search for news by keyword, topic, or entity name. Meilisearch provides fast, typo-tolerant search across multiple languages -- critical for an app serving 5 Indian languages with varied transliterations.

**What to build:**
- Meilisearch client wrapper for article indexing and querying
- Index articles with: title, summary (all languages), category, source, publish_time
- Multi-language search: query in any language returns relevant results
- Typo tolerance: handle common misspellings
- Search API: GET /api/search?q=query&language=en&limit=20
- Auto-index new articles as they are processed
- Faceted search: filter by category, source, date range

**Files to create/update:**
- src/search/meilisearch_client.py
- src/search/indexer.py
- src/api/search.py
- tests/test_search.py

**How to test locally:**
```bash
# Start Meilisearch
docker compose up -d meilisearch
# Index sample articles
python -c "
from src.search.indexer import SearchIndexer
indexer = SearchIndexer()
indexer.index_all()
print(f'Indexed {indexer.get_count()} articles')
"
# Test search
curl "http://localhost:8000/api/search?q=cricket&language=en&limit=10"
curl "http://localhost:8000/api/search?q=modi&language=hi&limit=10"
# Run tests
pytest tests/test_search.py -v
```

**Acceptance Criteria:**
- [ ] Articles indexed in Meilisearch with all language translations
- [ ] Search returns relevant results in < 50ms
- [ ] Typo tolerance handles 1-2 character errors
- [ ] Multi-language: English query finds English results, Hindi query finds Hindi results
- [ ] Faceted filtering by category, source, date range
- [ ] New articles auto-indexed when processed through pipeline
- [ ] GET /api/search returns snap metadata with pagination
- [ ] Empty query returns trending/recent articles

**Branch:** `feature/issue-18-meilisearch`
**Dependencies:** Issue 14

---

### Issue 19 - Build interaction system for like, comment, share, and bookmark

**Why:**
Social interactions make the app sticky and feed the recommendation engine. Likes, comments, shares, and bookmarks are both engagement features for users and signal sources for personalization.

**What to build:**
- Interaction API: like/unlike, bookmark/unbookmark, share (track), read (implicit)
- Comment system: create, list, delete own comments
- Read tracking: record when user opens a snap, time spent viewing
- Interaction counts: per-article like_count, comment_count, share_count, bookmark_count
- Rate limiting: max 1 like per article per user, max 100 comments per day per user
- Interaction events stored for recommendation engine

**Files to create/update:**
- src/api/interactions.py
- src/api/comments.py
- src/models/interaction.py (expand from Issue 2)
- tests/test_interactions.py

**How to test locally:**
```bash
# Like an article
curl -X POST -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/articles/123/like"
# Comment
curl -X POST -H "Authorization: Bearer <token>" \
  -d '{"text": "Great summary!"}' \
  "http://localhost:8000/api/articles/123/comments"
# Get comments
curl "http://localhost:8000/api/articles/123/comments?limit=20"
# Bookmark
curl -X POST -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/articles/123/bookmark"
# Track read
curl -X POST -H "Authorization: Bearer <token>" \
  -d '{"time_spent_seconds": 15}' \
  "http://localhost:8000/api/articles/123/read"
# Run tests
pytest tests/test_interactions.py -v
```

**Acceptance Criteria:**
- [ ] Like/unlike toggles correctly, prevents duplicate likes
- [ ] Bookmark/unbookmark toggles correctly
- [ ] Share tracking records share events without blocking user
- [ ] Read tracking records snap opens and time spent
- [ ] Comments: create, list (paginated), delete own
- [ ] Interaction counts updated atomically (no race conditions)
- [ ] Rate limiting: max 1 like per article, max 100 comments/day
- [ ] All interactions stored as events for recommendation engine
- [ ] GET /api/users/me/bookmarks returns bookmarked articles

**Branch:** `feature/issue-19-interactions`
**Dependencies:** Issues 4, 17

---

### Issue 20 - Build trending and category APIs with breaking news support

**Why:**
Users want to discover what is happening right now. Trending shows high-velocity news, categories let users browse by interest, and breaking news gets priority placement. These are the "Explore" page of our Instagram-like experience.

**What to build:**
- Trending API: articles with highest interaction velocity in last 1 hour
- Category API: list categories, top articles per category
- Breaking news detection: articles from last 30 minutes with velocity > threshold
- Explore API: trending + top per category + breaking news (combined endpoint for explore screen)
- Velocity computation: interactions per minute, stored in Redis
- Auto-refresh: trending scores recomputed every 5 minutes

**Files to create/update:**
- src/api/trending.py
- src/api/categories.py
- src/recommendation/trending.py
- tests/test_trending.py

**How to test locally:**
```bash
# Get trending
curl "http://localhost:8000/api/trending?language=en&limit=10"
# Get categories
curl "http://localhost:8000/api/categories"
# Get top articles in category
curl "http://localhost:8000/api/categories/sports/top?language=en&limit=10"
# Get explore page
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/explore?language=en"
# Check breaking news
curl "http://localhost:8000/api/breaking?language=en"
# Run tests
pytest tests/test_trending.py -v
```

**Acceptance Criteria:**
- [ ] Trending API returns articles ranked by interaction velocity (last 1 hour)
- [ ] Category API lists all categories with article counts
- [ ] Top articles per category returns best articles from last 24 hours
- [ ] Breaking news: articles < 30 min old with velocity > configurable threshold
- [ ] Explore endpoint combines: breaking (if any) + trending + top per category
- [ ] Velocity computed in Redis, refreshed every 5 minutes
- [ ] All endpoints support language filtering
- [ ] Response time < 100ms (Redis-cached)

**Branch:** `feature/issue-20-trending-categories`
**Dependencies:** Issues 17, 19

---

## M6: Recommendation Engine

---

### Issue 21 - Build content-based recommender using topic and category similarity

**Why:**
Content-based filtering is the foundation of personalization. If a user reads lots of sports news, show them more sports. If they engage with finance, prioritize finance. Simple but effective, and works from day one without needing other users' data.

**What to build:**
- User profile vector: weighted average of category/topic vectors from articles they engaged with
- Article scoring: cosine similarity between user profile and article category/topic vector
- Recency weighting: recent interactions weighted higher (exponential decay, half-life = 3 days)
- Category affinity tracker: per-category engagement rate for each user
- Cold start: use onboarding preferences until user has 20+ interactions

**Files to create/update:**
- src/recommendation/content_based.py
- src/recommendation/signals.py (interaction event processor)
- tests/test_content_based.py

**How to test locally:**
```bash
# Test content-based recommendations
python -c "
from src.recommendation.content_based import ContentBasedRecommender
rec = ContentBasedRecommender()
# Get recommendations for user
scores = rec.score_articles(user_id=1, candidate_articles=[...])
for article_id, score in sorted(scores.items(), key=lambda x: -x[1])[:10]:
    print(f'  Article {article_id}: score {score:.3f}')
"
# Run tests
pytest tests/test_content_based.py -v
```

**Acceptance Criteria:**
- [ ] User profile vector computed from engagement history
- [ ] Articles scored by cosine similarity to user profile
- [ ] Recent interactions weighted higher than older ones (exponential decay)
- [ ] Per-category affinity tracks engagement rate per category per user
- [ ] Cold start uses onboarding preferences (no crash on new users)
- [ ] Profile updates incrementally (not recomputed from scratch each time)
- [ ] Scoring 1000 articles for 1 user takes < 1 second
- [ ] User with sports-heavy history gets higher scores for sports articles

**Branch:** `feature/issue-21-content-based`
**Dependencies:** Issue 19

---

### Issue 22 - Build collaborative filtering with implicit feedback signals

**Why:**
Content-based filtering only recommends "more of the same." Collaborative filtering discovers unexpected connections: "users who liked X also liked Y." This is what makes Netflix and Instagram recommendations feel magical.

**What to build:**
- Implicit feedback matrix: users x articles, values = weighted engagement score
- Signal weights: read=1, time_spent>5s=2, like=3, bookmark=4, comment=5, share=7
- Algorithm: Alternating Least Squares (ALS) via implicit library
- Model training: batch retrain every 6 hours (or on significant new data)
- Recommendation generation: given user factors, score candidate articles
- Handle cold start: fall back to content-based for users with < 20 interactions

**Files to create/update:**
- src/recommendation/collaborative.py
- src/scheduler/jobs.py (add recommendation model retraining job)
- tests/test_collaborative.py

**How to test locally:**
```bash
# Train model
python -c "
from src.recommendation.collaborative import CollaborativeFilter
cf = CollaborativeFilter()
cf.train()  # trains on all interaction data
print(f'Model trained on {cf.num_users} users, {cf.num_items} items')
# Get recommendations
recs = cf.recommend(user_id=1, n=10)
for article_id, score in recs:
    print(f'  Article {article_id}: score {score:.3f}')
"
# Run tests
pytest tests/test_collaborative.py -v
```

**Acceptance Criteria:**
- [ ] Interaction matrix built from weighted engagement signals
- [ ] ALS model trains successfully on interaction data
- [ ] Model retrains every 6 hours via scheduler
- [ ] Recommendations differ from content-based (discovers cross-category items)
- [ ] Cold start: gracefully falls back to content-based for users with < 20 interactions
- [ ] Training on 10K interactions completes in < 60 seconds
- [ ] Model artifacts persisted to disk for fast restart
- [ ] Recommendation quality: liked articles rank higher than random

**Branch:** `feature/issue-22-collaborative-filtering`
**Dependencies:** Issue 21

---

### Issue 23 - Build hybrid recommendation scorer with diversity injection

**Why:**
Neither content-based nor collaborative filtering alone is sufficient. The hybrid scorer blends both with trending signals and adds diversity injection to prevent filter bubbles -- ensuring users discover new topics, not just echo chambers.

**What to build:**
- Hybrid scorer: weighted blend of content-based, collaborative, and trending scores
- Default weights: content_based=0.4, collaborative=0.35, trending=0.25 (configurable)
- Recency decay: newer articles get score boost, older articles decay
- Diversity injection: 20% of feed from underrepresented categories for the user
- Filter bubble prevention: track category distribution in recent feed, inject if too skewed
- Final feed ranking: hybrid_score * recency_factor, then interleave diversity picks

**Files to create/update:**
- src/recommendation/engine.py (expand from Issue 17)
- src/recommendation/diversity.py
- tests/test_recommendation_engine.py

**How to test locally:**
```bash
# Test hybrid scoring
python -c "
from src.recommendation.engine import RecommendationEngine
engine = RecommendationEngine()
feed = engine.get_feed(user_id=1, language='en', limit=20)
for item in feed:
    print(f'  {item.category}: {item.title[:50]} (score: {item.score:.3f})')
# Check diversity
categories = [item.category for item in feed]
from collections import Counter
print(f'Category distribution: {Counter(categories)}')
"
# Run tests
pytest tests/test_recommendation_engine.py -v
```

**Acceptance Criteria:**
- [ ] Hybrid score blends content-based, collaborative, and trending with configurable weights
- [ ] Recency decay boosts articles from last 4 hours, decays articles > 24 hours
- [ ] 20% of feed items are diversity picks (categories user has not engaged with recently)
- [ ] Feed never has > 50% articles from a single category
- [ ] Final feed is re-ranked: hybrid_score * recency_factor
- [ ] Feed generation for 1 user takes < 500ms
- [ ] A/B testable: weights and diversity ratio configurable per user segment
- [ ] Feed quality: engaged users see measurably different feeds than new users

**Branch:** `feature/issue-23-hybrid-scorer`
**Dependencies:** Issues 21, 22, 20

---

### Issue 24 - Build recommendation refresh scheduler and A/B test framework

**Why:**
Recommendations must stay fresh as new content arrives and user preferences evolve. The scheduler ensures feeds are recomputed regularly. A/B testing lets us experiment with different recommendation strategies to improve engagement.

**What to build:**
- Recommendation refresh scheduler: recompute top feed items per user every 30 minutes
- Redis-cached feeds: pre-computed feeds stored in Redis for fast API responses
- Invalidation: refresh user feed when they interact with new content
- A/B test framework: assign users to experiment groups, track different recommendation configs
- Metrics collection: click-through rate, time spent, diversity score per experiment group

**Files to create/update:**
- src/scheduler/jobs.py (add recommendation refresh job)
- src/recommendation/ab_testing.py
- src/recommendation/metrics.py
- tests/test_ab_testing.py

**How to test locally:**
```bash
# Test recommendation refresh
python -c "
from src.scheduler.jobs import refresh_recommendations
refresh_recommendations()
print('Recommendations refreshed for all active users')
"
# Test A/B framework
python -c "
from src.recommendation.ab_testing import ABTestManager
ab = ABTestManager()
# Create experiment
ab.create_experiment('diversity_ratio', variants={'control': 0.2, 'high_diversity': 0.4})
# Assign user
variant = ab.get_variant(user_id=1, experiment='diversity_ratio')
print(f'User 1 assigned to: {variant}')
"
# Run tests
pytest tests/test_ab_testing.py -v
```

**Acceptance Criteria:**
- [ ] Recommendation refresh runs every 30 minutes for active users
- [ ] Pre-computed feeds cached in Redis (top 50 items per user per language)
- [ ] Cache invalidated on significant user interaction (like, share, comment)
- [ ] A/B test framework assigns users to consistent experiment groups
- [ ] Metrics tracked per variant: CTR, avg time spent, diversity score
- [ ] At least one default experiment configured (diversity ratio)
- [ ] Refresh of 1000 user feeds completes in < 5 minutes
- [ ] API serves cached feed in < 50ms

**Branch:** `feature/issue-24-recommendation-scheduler`
**Dependencies:** Issue 23

---

## M7: Mobile App

---

### Issue 25 - Build React Native app scaffold with Expo and navigation

**Why:**
This is a mobile-first product. React Native with Expo gives us a real native app with swipe gestures, push notifications, and app store distribution -- things a web app cannot match for the news consumption experience.

**What to build:**
- Expo project initialization with TypeScript
- Navigation: tab navigator (Feed, Search, Bookmarks, Profile) + stack navigator for detail screens
- Theme system: light mode (white), with color palette for categories
- Auth flow: Google OAuth login screen -> onboarding -> main app
- API client: Axios/fetch wrapper with JWT token management
- State management: React Context or Zustand for user state
- Language picker component (affects all content display)

**Files to create/update:**
- frontend/App.tsx
- frontend/navigation/TabNavigator.tsx
- frontend/navigation/StackNavigator.tsx
- frontend/screens/ (placeholder screens for all routes)
- frontend/api/client.ts
- frontend/api/auth.ts
- frontend/context/AuthContext.tsx
- frontend/context/LanguageContext.tsx
- frontend/theme/colors.ts
- frontend/theme/typography.ts
- package.json, tsconfig.json, app.json

**How to test locally:**
```bash
cd frontend
npx expo install
npx expo start
# Scan QR code with Expo Go on phone, or press 'i' for iOS simulator / 'a' for Android emulator
# Verify: login screen shows, tabs navigate, language picker works
```

**Acceptance Criteria:**
- [ ] Expo project builds and runs on iOS simulator and Android emulator
- [ ] Tab navigation: Feed, Search, Bookmarks, Profile tabs
- [ ] Stack navigation: screens push/pop correctly
- [ ] Google OAuth login flow: tap "Sign in with Google" -> Google consent -> redirect back -> JWT stored
- [ ] Onboarding screen: language selection + category preferences (shown on first login only)
- [ ] API client attaches JWT to all requests, handles token refresh
- [ ] Language context: changing language updates all content
- [ ] Light theme with consistent typography and spacing

**Branch:** `feature/issue-25-rn-scaffold`
**Dependencies:** Issue 4

---

### Issue 26 - Build swipe feed screen with vertical swipe and infinite scroll

**Why:**
The swipe feed IS the product experience. Users open the app and vertically swipe through full-screen news snaps -- exactly like Instagram Reels or Inshorts. Smooth, native-feeling swipe gestures are critical.

**What to build:**
- Vertical swipe feed using FlatList with pagingEnabled (or react-native-pager-view)
- Each page is a full-screen SnapCard component showing the news snap
- SnapCard: image at top, category badge, summary text, source + time ago, interaction bar at bottom
- Infinite scroll: load next batch when user reaches last 3 items
- Pull-to-refresh: pull down to get latest news
- Loading skeleton: shimmer effect while snaps load
- Snap view tracking: record when user views each snap (for recommendation signals)

**Files to create/update:**
- frontend/screens/FeedScreen.tsx
- frontend/components/SnapCard.tsx
- frontend/components/SwipeView.tsx
- frontend/components/InteractionBar.tsx
- frontend/components/SkeletonLoader.tsx
- frontend/api/feed.ts
- frontend/hooks/useFeed.ts

**How to test locally:**
```bash
cd frontend
npx expo start
# Open on device/simulator
# Verify: swipe up/down navigates between snaps
# Verify: infinite scroll loads more content
# Verify: pull-to-refresh fetches latest
# Verify: interaction bar shows like/comment/share/bookmark
```

**Acceptance Criteria:**
- [ ] Vertical swipe moves between full-screen snap cards
- [ ] Swipe gesture is smooth (60 FPS, no jank)
- [ ] SnapCard displays: image, category badge, summary, source, time ago
- [ ] Infinite scroll: next page loads when 3 items from end
- [ ] Pull-to-refresh fetches latest snaps
- [ ] Loading skeleton shown while content loads
- [ ] Each snap view tracked (sent to backend for recommendation)
- [ ] Snaps display correctly in all 5 languages (correct font and script)
- [ ] Handles empty feed state (no content available)

**Branch:** `feature/issue-26-swipe-feed`
**Dependencies:** Issues 17, 25

---

### Issue 27 - Build search and explore screen with category chips and trending

**Why:**
The explore screen is how users discover news beyond their feed. Instagram-style: search bar at top, category chips for quick filtering, trending grid below. This drives engagement beyond the main feed.

**What to build:**
- Search screen with text input and real-time search results
- Search results displayed as compact snap cards (image + title + source)
- Category chips: horizontal scrollable row of category buttons
- Trending section: grid of trending snap cards (2 columns)
- Recent searches: stored locally, shown when search bar is empty
- Search debounce: wait 300ms after typing before API call

**Files to create/update:**
- frontend/screens/SearchScreen.tsx
- frontend/components/SearchBar.tsx
- frontend/components/CategoryChips.tsx
- frontend/components/TrendingGrid.tsx
- frontend/components/CompactSnapCard.tsx
- frontend/api/search.ts
- frontend/hooks/useSearch.ts

**How to test locally:**
```bash
cd frontend
npx expo start
# Navigate to Search tab
# Verify: search bar accepts input, shows results after typing
# Verify: category chips filter results
# Verify: trending grid shows popular articles
# Verify: tapping a result opens full snap
```

**Acceptance Criteria:**
- [ ] Search bar with 300ms debounce triggers API search
- [ ] Results displayed as compact cards (image thumbnail + title + source + time)
- [ ] Category chips: horizontal scroll, tapping filters search/explore results
- [ ] Trending grid: 2-column layout with top trending snaps
- [ ] Recent searches stored locally and shown when input is empty
- [ ] Empty state: shows trending when no search query
- [ ] Tapping a search result navigates to full snap view
- [ ] Search works in all 5 languages

**Branch:** `feature/issue-27-search-explore`
**Dependencies:** Issues 18, 20, 25

---

### Issue 28 - Build social features UI with like animation and comment sheet

**Why:**
Social features make the app sticky. A satisfying like animation, easy comment access, and one-tap sharing encourage users to interact -- and every interaction feeds the recommendation engine.

**What to build:**
- Like button with heart animation (tap to like, double-tap on snap card to like)
- Comment bottom sheet: slides up from bottom, shows comments, input field at bottom
- Share: native share sheet (share snap image + link)
- Bookmark button with saved animation
- Interaction counts displayed on each snap
- Haptic feedback on like and bookmark

**Files to create/update:**
- frontend/components/InteractionBar.tsx (expand from Issue 26)
- frontend/components/LikeButton.tsx (with animation)
- frontend/components/CommentSheet.tsx
- frontend/components/ShareButton.tsx
- frontend/components/BookmarkButton.tsx
- frontend/api/interactions.ts
- frontend/hooks/useInteractions.ts

**How to test locally:**
```bash
cd frontend
npx expo start
# On feed screen:
# Verify: tap heart -> fills red with animation, count increments
# Verify: double-tap snap -> heart animation overlay
# Verify: tap comment icon -> bottom sheet slides up with comments
# Verify: can type and submit comment
# Verify: tap share -> native share sheet opens
# Verify: tap bookmark -> saves with animation
```

**Acceptance Criteria:**
- [ ] Like button: tap toggles like with heart fill animation
- [ ] Double-tap on snap card triggers like with floating heart animation
- [ ] Comment sheet: bottom sheet with comment list + input field
- [ ] Comments load with pagination (scroll for more)
- [ ] New comment appears instantly in list after submission
- [ ] Share: opens native share sheet with snap preview and link
- [ ] Bookmark: tap toggles bookmark with subtle animation
- [ ] Interaction counts (likes, comments) update in real-time
- [ ] Haptic feedback on like and bookmark (iOS and Android)

**Branch:** `feature/issue-28-social-features`
**Dependencies:** Issues 19, 26

---

### Issue 29 - Build profile, settings, and onboarding screens

**Why:**
Users need to manage their account, change language, update category preferences, and control notifications. The onboarding flow ensures new users set up preferences that seed the recommendation engine.

**What to build:**
- Onboarding flow (shown once): welcome -> select primary language -> select 3+ categories -> done
- Profile screen: user avatar (from Google), name, email, stats (articles read, likes, streak)
- Settings screen: language preference, category preferences (editable), notification settings, logout
- Bookmarks screen: list of bookmarked snaps with remove option
- Reading history: recent snaps viewed (last 7 days)

**Files to create/update:**
- frontend/screens/OnboardingScreen.tsx
- frontend/screens/ProfileScreen.tsx
- frontend/screens/SettingsScreen.tsx
- frontend/screens/BookmarksScreen.tsx
- frontend/screens/HistoryScreen.tsx
- frontend/components/LanguagePicker.tsx
- frontend/components/CategorySelector.tsx
- frontend/api/users.ts

**How to test locally:**
```bash
cd frontend
npx expo start
# First login: verify onboarding flow shows
# Profile tab: verify user info, stats displayed
# Settings: change language -> verify feed updates
# Settings: update categories -> verify feed reflects changes
# Bookmarks: verify saved articles listed, can remove
```

**Acceptance Criteria:**
- [ ] Onboarding: 3-step flow (welcome -> language -> categories -> done)
- [ ] Onboarding only shown on first login (is_onboarded flag)
- [ ] Profile shows: Google avatar, name, email, articles read count, like count
- [ ] Settings: language picker changes feed language immediately
- [ ] Settings: category preferences editable (minimum 3 selected)
- [ ] Settings: notification toggle (on/off)
- [ ] Settings: logout clears JWT and navigates to login
- [ ] Bookmarks: paginated list, swipe or tap to remove
- [ ] Reading history: last 7 days of viewed snaps

**Branch:** `feature/issue-29-profile-settings`
**Dependencies:** Issues 25, 28

---

## M8: Production Readiness

---

### Issue 30 - Build push notification system for breaking news and digests

**Why:**
Push notifications bring users back to the app. Breaking news alerts ensure users hear important news first from us. Daily digests maintain engagement even when users forget to open the app.

**What to build:**
- Firebase Cloud Messaging (FCM) integration for push notifications
- Breaking news notifications: auto-trigger when article velocity > threshold
- Daily digest: morning notification with top 3 stories in user's language
- Notification preferences: users can enable/disable per type (breaking, digest, trending)
- FCM token management: store per user, handle token refresh
- Notification API: GET /api/notifications (in-app notification history)

**Files to create/update:**
- src/api/notifications.py
- src/utils/push_notifications.py (FCM client)
- src/scheduler/jobs.py (add digest job)
- frontend/utils/notifications.ts (FCM token registration)
- tests/test_notifications.py

**How to test locally:**
```bash
# Test push notification
python -c "
from src.utils.push_notifications import send_notification
send_notification(
    user_id=1,
    title='Breaking: India wins World Cup',
    body='India defeated Australia by 6 wickets in the final',
    data={'article_id': '123'}
)
print('Notification sent')
"
# Test digest generation
python -c "
from src.scheduler.jobs import generate_daily_digest
generate_daily_digest()
print('Daily digest sent to all users')
"
# Run tests
pytest tests/test_notifications.py -v
```

**Acceptance Criteria:**
- [ ] FCM integration sends push notifications to iOS and Android
- [ ] Breaking news: auto-notifies when article velocity exceeds threshold
- [ ] Daily digest: sent at 8 AM IST with top 3 stories in user's preferred language
- [ ] Notification preferences: users can disable breaking, digest, or all
- [ ] FCM tokens stored per user, refreshed on token change
- [ ] In-app notification history: GET /api/notifications (paginated)
- [ ] Tapping notification opens relevant article in app
- [ ] Notifications respect user's language preference

**Branch:** `feature/issue-30-push-notifications`
**Dependencies:** Issues 20, 29

---

### Issue 31 - Build data cleanup scheduler with 2-week retention policy

**Why:**
Mobile news consumers rarely revisit old news. Keeping stale data wastes storage, slows queries, and clutters search results. A 2-week retention policy keeps the system lean and fast.

**What to build:**
- Cleanup scheduler: daily job at 3:00 AM IST
- Soft delete: mark articles > 14 days old as archived
- Hard delete: remove articles > 21 days old + associated snaps, comments, images
- Aggregate before delete: save interaction aggregates (category weights) to user profile before removing raw events
- Orphan cleanup: remove snap images with no associated article
- Database maintenance: VACUUM ANALYZE weekly
- Search index cleanup: remove deleted articles from Meilisearch
- Cleanup report: log articles deleted, storage reclaimed, errors

**Files to create/update:**
- src/scheduler/cleanup.py
- src/scheduler/jobs.py (add cleanup jobs)
- src/api/admin.py (add cleanup status endpoint)
- tests/test_cleanup.py

**How to test locally:**
```bash
# Test cleanup (dry run)
python -c "
from src.scheduler.cleanup import DataCleaner
cleaner = DataCleaner()
report = cleaner.run(dry_run=True)
print(f'Would archive: {report.articles_to_archive}')
print(f'Would delete: {report.articles_to_delete}')
print(f'Would remove: {report.images_to_remove}')
print(f'Storage to reclaim: {report.storage_bytes / 1024 / 1024:.1f} MB')
"
# Run actual cleanup
python -c "
from src.scheduler.cleanup import DataCleaner
cleaner = DataCleaner()
report = cleaner.run(dry_run=False)
print(f'Archived: {report.articles_archived}')
print(f'Deleted: {report.articles_deleted}')
"
# Run tests
pytest tests/test_cleanup.py -v
```

**Acceptance Criteria:**
- [ ] Daily cleanup runs at 3:00 AM IST via scheduler
- [ ] Articles > 14 days: marked as archived (soft delete)
- [ ] Articles > 21 days: hard deleted with cascading removal of snaps, comments, images
- [ ] User interaction aggregates preserved before raw event deletion
- [ ] Orphan snap images removed from disk
- [ ] Meilisearch index updated (deleted articles removed)
- [ ] Weekly VACUUM ANALYZE on PostgreSQL
- [ ] Cleanup report logged: articles archived, deleted, storage reclaimed
- [ ] Dry run mode available (reports what would be deleted without actually deleting)

**Branch:** `feature/issue-31-data-cleanup`
**Dependencies:** Issue 8

---

### Issue 32 - Build admin monitoring dashboard for pipeline health

**Why:**
A news app with broken scrapers serves stale content. The admin dashboard gives the team real-time visibility into: which sources are healthy, how many articles are flowing through, where the pipeline is failing.

**What to build:**
- Admin dashboard (React, separate from mobile app -- web-based)
- Source health panel: per-source status (healthy/unhealthy), last scrape time, error rate
- Pipeline throughput: articles scraped, deduplicated, summarized, translated per hour (charts)
- Content stats: total articles, snaps, by language, by category
- Error log: recent scrape/summarize/translate failures with details
- System health: database size, Redis memory, Meilisearch index size
- Protected by admin role (not accessible to regular users)

**Files to create/update:**
- src/api/admin.py (expand with dashboard data endpoints)
- frontend/admin/ (simple React web dashboard, separate from mobile app)
- frontend/admin/SourceHealth.tsx
- frontend/admin/PipelineChart.tsx
- frontend/admin/ErrorLog.tsx
- frontend/admin/SystemHealth.tsx
- tests/test_admin_api.py

**How to test locally:**
```bash
# Start backend
uvicorn src.api.main:app --reload
# View admin dashboard
open http://localhost:8000/admin
# Check API endpoints
curl -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/admin/dashboard
curl -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/admin/source-health
curl -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/admin/pipeline-throughput
# Run tests
pytest tests/test_admin_api.py -v
```

**Acceptance Criteria:**
- [ ] Admin dashboard accessible via web browser at /admin
- [ ] Source health: each source shows status, last scrape time, success/error count
- [ ] Pipeline throughput chart: articles per hour (scraped, deduped, summarized, translated)
- [ ] Content stats: total articles and snaps by language and category
- [ ] Error log: last 100 pipeline errors with timestamp, source, error message
- [ ] System health: database size, Redis memory usage, Meilisearch index size
- [ ] Dashboard protected: only admin role users can access
- [ ] Auto-refresh every 60 seconds

**Branch:** `feature/issue-32-admin-dashboard`
**Dependencies:** Issue 8

---

### Issue 33 - E2E testing, Redis caching, performance optimization, and deployment

**Why:**
The final milestone brings everything together. E2E tests verify the full pipeline works end-to-end. Redis caching ensures fast responses. Performance optimization handles production load. Docker deployment makes it ship-ready.

**What to build:**
- E2E test suite: scrape -> dedup -> summarize -> translate -> snap -> feed -> search
- Redis caching layer: cache feed responses, search results, trending, category counts
- Cache invalidation strategy: on new content, on user interaction
- Performance benchmarks: feed API < 200ms, search < 50ms, snap generation < 2s
- Docker production config: multi-stage build, environment-specific configs
- Deployment guide: Railway/Render with PostgreSQL, Redis, Meilisearch add-ons
- API rate limiting: 100 requests/minute per user
- CORS configuration for mobile app
- Health check endpoint: GET /health

**Files to create/update:**
- tests/test_e2e.py
- src/api/middleware.py (add caching, rate limiting, CORS)
- src/utils/cache.py (Redis caching utilities)
- Dockerfile (production multi-stage build)
- docker-compose.prod.yml
- docs/deployment.md
- docs/api.md (API documentation)

**How to test locally:**
```bash
# Run E2E tests
pytest tests/test_e2e.py -v --timeout=120
# Benchmark API
python -c "
import time, requests
# Feed benchmark
start = time.time()
for _ in range(100):
    requests.get('http://localhost:8000/api/feed?language=en&limit=20',
                 headers={'Authorization': 'Bearer <token>'})
elapsed = (time.time() - start) / 100
print(f'Feed avg: {elapsed*1000:.0f}ms')
"
# Docker production build
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
# Health check
curl http://localhost:8000/health
# Run all tests
pytest tests/ -v
```

**Acceptance Criteria:**
- [ ] E2E test passes: full pipeline from scrape to feed delivery
- [ ] Feed API response < 200ms (cached)
- [ ] Search API response < 50ms
- [ ] Redis caching on: feed, search, trending, categories
- [ ] Cache invalidation works correctly (new content appears in feed)
- [ ] API rate limiting: 100 req/min per user, 429 response on exceed
- [ ] Docker production build: multi-stage, < 500MB image
- [ ] Deployment guide covers Railway/Render with all services
- [ ] Health check endpoint returns service status (db, redis, meilisearch)
- [ ] CORS configured for mobile app domains
- [ ] All tests pass (unit + integration + E2E)

**Branch:** `feature/issue-33-deployment`
**Dependencies:** All previous issues

---

NST Engineering - NewsSnap AI | Summer Profile Building Drive 2026
