#!/bin/bash
# NewsSnap AI - Create all 33 GitHub issues
# Requires: gh CLI authenticated (gh auth login)
# Usage: bash scripts/create_github_issues.sh

REPO="newton-school-ai/newssnap-ai"

create_issue() {
  local num=$1
  local title=$2
  local milestone=$3
  local labels=$4
  local body=$5

  local full_title="Issue $num - $title"
  echo "Creating: $full_title"
  gh issue create --repo "$REPO" \
    --title "$full_title" \
    --milestone "$milestone" \
    --label "$labels" \
    --body "$body"
  sleep 1
}

# --- M1: Project Scaffold, DB, and Auth ---

create_issue 1 "Initialize repo scaffold, CI workflow, Docker setup" \
  "M1: Project Scaffold, DB, and Auth" "m1,infra" \
  "## Why
Every production project needs a clean foundation: consistent directory structure, automated CI to catch bugs early, and Docker for reproducible environments.

## What to build
- Complete directory structure matching PROJECT_CONTEXT.md
- GitHub Actions CI workflow: lint (ruff) + test (pytest) on every PR to dev
- Dockerfile for backend (Python 3.11, FastAPI)
- docker-compose.yml with backend, PostgreSQL, Redis, Meilisearch services
- Pre-commit hooks for linting

## Files to create
- .github/workflows/ci.yml
- Dockerfile
- docker-compose.yml
- All src/ sub-package __init__.py files
- pyproject.toml for linting config

## How to test locally
\`\`\`bash
ruff check src/
pytest tests/ -v
docker compose build
docker compose up -d
docker compose ps
\`\`\`

## Acceptance Criteria
- [ ] Directory structure matches PROJECT_CONTEXT.md
- [ ] ruff check src/ passes with zero errors
- [ ] pytest tests/ runs and passes
- [ ] docker compose up -d starts all services
- [ ] CI triggers on PR to dev and passes
- [ ] Pre-commit hook runs linter

## Branch: feature/issue-1-scaffold
## Dependencies: None"

create_issue 2 "Design database schema, Alembic migrations, and seed data" \
  "M1: Project Scaffold, DB, and Auth" "m1,infra" \
  "## Why
The entire application depends on a well-designed database. Articles, snaps, users, interactions -- all need proper tables with indexes.

## What to build
- SQLAlchemy models: User, Article, Snap, Story, Source, Category, Interaction, Comment, Notification, UserPreference
- Alembic migration setup with initial migration
- Seed data script: sample sources, categories, test user
- Database indexes for common queries

## Files to create
- src/models/user.py, article.py, snap.py, story.py, source.py, category.py, interaction.py, notification.py, base.py
- alembic.ini, alembic/env.py, alembic/versions/001_initial_schema.py
- scripts/seed.py

## How to test locally
\`\`\`bash
docker compose up -d db
alembic upgrade head
python scripts/seed.py
\`\`\`

## Acceptance Criteria
- [ ] All 10 SQLAlchemy models defined with proper relationships
- [ ] alembic upgrade head creates all tables without errors
- [ ] Indexes exist on key columns (publish_time, language, user_id, etc.)
- [ ] Seed script creates 20+ sources, all 19 categories, 1 test user
- [ ] Foreign keys enforce referential integrity
- [ ] All models have created_at and updated_at timestamps

## Branch: feature/issue-2-db-schema
## Dependencies: Issue 1"

create_issue 3 "Build news source configuration and registry system" \
  "M1: Project Scaffold, DB, and Auth" "m1,scraper" \
  "## Why
The scraper needs to know HOW to scrape each source. A registry system makes it easy to add new sources without changing code.

## What to build
- Source configuration schema (JSON format)
- Source registry that loads configs from JSON files and database
- Source health tracker
- API endpoints to list sources and check health
- Initial configs for 10+ sources

## Files to create
- src/scrapers/source_registry.py
- src/scrapers/source_configs/ (10+ JSON files)
- src/api/sources.py
- tests/test_source_registry.py

## How to test locally
\`\`\`bash
python -c \"from src.scrapers.source_registry import SourceRegistry; print(len(SourceRegistry().get_all_sources()))\"
curl http://localhost:8000/api/sources
pytest tests/test_source_registry.py -v
\`\`\`

## Acceptance Criteria
- [ ] At least 10 source configs created (mix of Playwright, RSS, static)
- [ ] SourceRegistry loads from both JSON files and database
- [ ] Source health tracking records last_scrape_time, success_count, error_count
- [ ] GET /api/sources returns all sources with health status
- [ ] Adding a new source requires only creating a JSON config file

## Branch: feature/issue-3-source-config
## Dependencies: Issue 2"

create_issue 4 "Build user auth API with Google OAuth and JWT" \
  "M1: Project Scaffold, DB, and Auth" "m1,infra" \
  "## Why
Every user needs an account for personalized recommendations and interactions. Google OAuth is the standard -- zero friction signup.

## What to build
- Google OAuth 2.0 flow (consent -> auth code -> profile -> JWT)
- JWT tokens: 24h access + 7d refresh
- User onboarding: language selection + category preferences
- Protected route middleware
- User profile API

## Files to create
- src/api/auth.py
- src/api/users.py
- src/api/middleware.py
- src/utils/auth_utils.py
- tests/test_auth.py

## How to test locally
\`\`\`bash
open http://localhost:8000/auth/google
curl -H \"Authorization: Bearer <token>\" http://localhost:8000/api/users/me
pytest tests/test_auth.py -v
\`\`\`

## Acceptance Criteria
- [ ] Google OAuth flow works end-to-end
- [ ] JWT access token expires in 24 hours, refresh in 7 days
- [ ] Protected routes return 401 without valid JWT
- [ ] First-time users flagged as needing onboarding
- [ ] Onboarding saves language and 3+ category selections
- [ ] Token refresh endpoint works correctly

## Branch: feature/issue-4-google-oauth
## Dependencies: Issue 2"

# --- M2: News Scraping Pipeline ---

create_issue 5 "Build Playwright-based web scraper for JS-rendered news sites" \
  "M2: News Scraping Pipeline" "m2,scraper" \
  "## Why
Most Indian news websites are React/Next.js and require JavaScript execution. Playwright renders the full page like a real browser.

## What to build
- Playwright scraper: navigate to article lists, extract links, visit each for full content
- Configurable via source config JSON
- Rate limiting, rotating user agents, retry with exponential backoff
- Headless browser pool management

## Files to create
- src/scrapers/playwright_scraper.py
- src/scrapers/browser_pool.py
- tests/test_playwright_scraper.py

## Acceptance Criteria
- [ ] Extracts articles from 5+ JS-rendered news sites
- [ ] Each article has: title, body, image_url, source_url, publish_time, category
- [ ] Rate limiting enforced (configurable delay per domain)
- [ ] Rotating user agents (10+ agents)
- [ ] Failed requests retry 3x with exponential backoff
- [ ] Browser pool reuses Playwright instances

## Branch: feature/issue-5-playwright-scraper
## Dependencies: Issue 3"

create_issue 6 "Build RSS and API scraper for feed-based news sources" \
  "M2: News Scraping Pipeline" "m2,scraper" \
  "## Why
Some sites offer RSS/Atom feeds which are faster and lighter than full page rendering.

## What to build
- RSS/Atom feed parser using feedparser
- Support for full-content and link-only feeds
- httpx + BeautifulSoup for static page fetching
- Normalize to same Article schema as Playwright scraper

## Files to create
- src/scrapers/rss_scraper.py
- src/scrapers/static_scraper.py
- tests/test_rss_scraper.py

## Acceptance Criteria
- [ ] RSS scraper parses Atom and RSS 2.0 feeds
- [ ] Link-only feeds: body fetched via httpx + BeautifulSoup
- [ ] Normalized output matches Playwright scraper schema
- [ ] Date parsing handles multiple formats
- [ ] At least 3 RSS-based sources working

## Branch: feature/issue-6-rss-scraper
## Dependencies: Issue 3"

create_issue 7 "Build article parser and content normalizer" \
  "M2: News Scraping Pipeline" "m2,scraper" \
  "## Why
Raw scraped content is messy. The parser must extract clean, structured article data regardless of source format.

## What to build
- Article parser using newspaper3k + custom extraction
- Content normalizer: strip HTML, remove ads/navigation
- Image extractor, category detector, language detector, metadata extractor

## Files to create
- src/scrapers/article_parser.py
- src/utils/text_utils.py
- src/utils/image_utils.py
- tests/test_article_parser.py

## Acceptance Criteria
- [ ] Clean body text with no HTML tags, ads, or navigation
- [ ] Lead image extracted from og:image with fallback
- [ ] Category assigned from URL patterns and content keywords
- [ ] Language detection verifies article matches source language
- [ ] Articles with body < 100 words flagged as incomplete

## Branch: feature/issue-7-article-parser
## Dependencies: Issues 5, 6"

create_issue 8 "Build scrape scheduler with monitoring and error handling" \
  "M2: News Scraping Pipeline" "m2,scraper,infra" \
  "## Why
The scrape pipeline must run every 10 minutes, handle failures gracefully, and provide visibility into health.

## What to build
- APScheduler running every 10 minutes
- Source rotation across the interval
- Pipeline: scrape -> parse -> store
- Error handling: mark unhealthy after 5 failures, cooldown
- Health monitoring API

## Files to create
- src/scheduler/jobs.py
- src/scheduler/scrape_pipeline.py
- src/api/admin.py
- tests/test_scheduler.py

## Acceptance Criteria
- [ ] Scheduler triggers every 10 minutes
- [ ] Sources spread across interval (not all at once)
- [ ] Articles stored in database with all fields
- [ ] Source marked unhealthy after 5 consecutive failures
- [ ] GET /api/admin/scrape-health returns per-source metrics
- [ ] Scheduler survives individual source failures

## Branch: feature/issue-8-scrape-scheduler
## Dependencies: Issues 5, 6, 7"

# --- M3: AI Content Pipeline ---

create_issue 9 "Build embedding-based deduplication agent" \
  "M3: AI Content Pipeline" "m3,agent" \
  "## Why
Multiple sources report the same events. Without dedup, users see 5 versions of the same news.

## What to build
- Embedding generator using sentence-transformers (all-MiniLM-L6-v2)
- Cosine similarity > 0.85 = duplicate
- Keep article from highest-priority source, link others as 'also reported by'
- Store embeddings in database

## Files to create
- src/agents/dedup_agent.py
- alembic/versions/002_add_embeddings.py
- tests/test_dedup_agent.py

## Acceptance Criteria
- [ ] Correctly identifies paraphrased duplicates (similarity > 0.85)
- [ ] Unique articles pass through
- [ ] Primary article from highest-priority source
- [ ] Comparison window configurable (default 48 hours)
- [ ] Batch processes 100+ articles in < 5 seconds

## Branch: feature/issue-9-dedup-agent
## Dependencies: Issue 8"

create_issue 10 "Build story clustering agent for related articles" \
  "M3: AI Content Pipeline" "m3,agent" \
  "## Why
Beyond duplicates, multiple unique articles often cover the same story. Clustering prevents feed repetition.

## What to build
- DBSCAN clustering on article embeddings
- Each cluster becomes a Story with primary and related articles
- New articles checked against existing stories

## Files to create
- src/agents/story_clusterer.py
- src/api/stories.py
- tests/test_story_clusterer.py

## Acceptance Criteria
- [ ] DBSCAN groups related articles into stories
- [ ] Each story has one primary and 0+ related articles
- [ ] New articles checked against existing stories
- [ ] GET /api/stories/{id} returns story with related articles
- [ ] Clustering runs in < 10 seconds for 500 articles

## Branch: feature/issue-10-story-clustering
## Dependencies: Issue 9"

create_issue 11 "Build LLM summarizer agent for crisp 1-paragraph summaries" \
  "M3: AI Content Pipeline" "m3,agent" \
  "## Why
Core value proposition. Users want news in 60 seconds, not 6-minute articles.

## What to build
- LangGraph summarizer agent using Groq LLM
- Category-aware prompts (finance, sports, politics styles)
- Quality validation: 60-80 words, factual, no clickbait
- Retry logic for failed quality checks

## Files to create
- src/agents/summarizer_agent.py
- src/agents/supervisor.py
- tests/test_summarizer_agent.py

## Acceptance Criteria
- [ ] Summaries are 60-80 words
- [ ] Key facts preserved (who, what, when, where, why)
- [ ] Category-aware prompts produce different styles
- [ ] Quality check rejects bad outputs (max 2 retries)
- [ ] Batch: 20 articles in < 30 seconds via Groq

## Branch: feature/issue-11-summarizer-agent
## Dependencies: Issue 10"

create_issue 12 "Build content quality filter to reject clickbait and spam" \
  "M3: AI Content Pipeline" "m3,agent" \
  "## Why
Not every scraped article deserves a snap. Filter clickbait, spam, and incomplete content before summarization.

## What to build
- Quality scoring: content length, title/body coherence, completeness
- Clickbait detector, sponsored content filter
- Configurable quality threshold
- Admin API for rejected articles

## Files to create
- src/agents/quality_filter.py
- tests/test_quality_filter.py

## Acceptance Criteria
- [ ] Clickbait articles rejected
- [ ] Articles with body < 100 words rejected
- [ ] Sponsored content detected and filtered
- [ ] Quality threshold configurable (default 0.4)
- [ ] GET /api/admin/rejected-articles returns rejections with reasons

## Branch: feature/issue-12-quality-filter
## Dependencies: Issue 9"

# --- M4: Translation and Snap Generation ---

create_issue 13 "Build multi-language translator agent for 5 Indian languages" \
  "M4: Translation and Snap Generation" "m4,agent" \
  "## Why
India has hundreds of millions who prefer native language content. 5 languages dramatically expands reach.

## What to build
- LangGraph translator using Groq LLM
- Languages: English, Hindi, Tamil, Telugu, Kannada
- Natural (not literal) translation with language-specific prompts
- Back-translation quality check
- IndicTrans2 fallback

## Files to create
- src/agents/translator_agent.py
- src/utils/language_utils.py
- tests/test_translator_agent.py

## Acceptance Criteria
- [ ] Translations for all 5 languages
- [ ] Natural-sounding output (not word-by-word)
- [ ] Back-translation quality check passes 90%+
- [ ] IndicTrans2 fallback works when Groq unavailable
- [ ] Batch: 20 summaries to all 5 languages in < 60 seconds

## Branch: feature/issue-13-translator-agent
## Dependencies: Issue 11"

create_issue 14 "Build snap image generator with white background layout" \
  "M4: Translation and Snap Generation" "m4,snaps" \
  "## Why
News snaps are the product's visual identity. Clean, consistent, mobile-optimized cards.

## What to build
- Snap generator using Pillow
- Layout: white bg, 1080x1920, lead image, category badge, summary, source
- Text auto-wrap and font scaling
- Generate for all language versions

## Files to create
- src/snaps/snap_generator.py
- src/snaps/image_handler.py
- tests/test_snap_generator.py

## Acceptance Criteria
- [ ] 1080x1920 pixels (9:16 mobile aspect)
- [ ] White background with clean typography
- [ ] Lead image at top in 16:9 ratio
- [ ] Summary text auto-wraps and scales
- [ ] Source and time-ago at bottom
- [ ] Works for all 5 languages
- [ ] File size < 500KB

## Branch: feature/issue-14-snap-generator
## Dependencies: Issue 13"

create_issue 15 "Build image extraction and processing pipeline" \
  "M4: Translation and Snap Generation" "m4,snaps" \
  "## Why
Snaps need compelling images. Pipeline must reliably extract, validate, resize, and provide fallbacks.

## What to build
- Image extractor (og:image, first large image, favicon fallback)
- Validator (reject small, broken, generic images)
- Resizer (16:9 crop), optimizer (< 500KB)
- Category placeholder system, image cache

## Files to create
- src/snaps/image_handler.py (expand)
- frontend/assets/placeholders/
- tests/test_image_handler.py

## Acceptance Criteria
- [ ] Extracts lead image from og:image with fallbacks
- [ ] Rejects images < 200x200
- [ ] Resizes to 16:9 with smart cropping
- [ ] Category placeholders for all 19 categories
- [ ] Image cache prevents re-downloading

## Branch: feature/issue-15-image-pipeline
## Dependencies: Issue 14"

create_issue 16 "Build snap template system for different content categories" \
  "M4: Translation and Snap Generation" "m4,snaps" \
  "## Why
Different news categories benefit from different layouts. Templates make snaps more engaging per category.

## What to build
- Template config system (JSON-based)
- Templates: General, Finance, Sports, Entertainment, Politics, Technology
- Auto-select by article category
- Custom colors per category

## Files to create
- src/snaps/templates/ (6 JSON configs)
- src/snaps/template_renderer.py
- tests/test_template_renderer.py

## Acceptance Criteria
- [ ] 8 template types covering all 19 categories
- [ ] Each has unique layout and color scheme
- [ ] Auto-selected by article category
- [ ] Templates as JSON configs (no hardcoded layouts)
- [ ] All produce valid 1080x1920 images
- [ ] Work in all 5 languages

## Branch: feature/issue-16-snap-templates
## Dependencies: Issues 14, 15"

# --- M5: Feed API, Search, and Interactions ---

create_issue 17 "Build personalized feed API with pagination and filtering" \
  "M5: Feed API, Search, and Interactions" "m5,infra" \
  "## Why
The feed is the product. Users see personalized news snaps with smooth infinite scroll.

## What to build
- GET /api/feed with cursor-based pagination
- Filters: language (required), categories, time range
- Default feed for new users (trending + preferences)
- Redis caching for pre-computed feeds

## Files to create
- src/api/feed.py
- src/recommendation/engine.py (basic)
- tests/test_feed_api.py

## Acceptance Criteria
- [ ] Cursor-based pagination
- [ ] Language filter required
- [ ] New users get trending + preference-based feed
- [ ] Response time < 200ms (cached)
- [ ] Handles end-of-feed gracefully

## Branch: feature/issue-17-feed-api
## Dependencies: Issues 4, 14"

create_issue 18 "Build Meilisearch integration for multi-language search" \
  "M5: Feed API, Search, and Interactions" "m5,search" \
  "## Why
Users need fast, typo-tolerant search across 5 languages.

## What to build
- Meilisearch client for indexing and querying
- Multi-language search with typo tolerance
- GET /api/search endpoint
- Auto-index new articles
- Faceted search by category, source, date

## Files to create
- src/search/meilisearch_client.py
- src/search/indexer.py
- src/api/search.py
- tests/test_search.py

## Acceptance Criteria
- [ ] Articles indexed with all language translations
- [ ] Search results in < 50ms
- [ ] Typo tolerance (1-2 chars)
- [ ] Multi-language search works
- [ ] Auto-indexing on new articles
- [ ] Faceted filtering

## Branch: feature/issue-18-meilisearch
## Dependencies: Issue 14"

create_issue 19 "Build interaction system for like, comment, share, and bookmark" \
  "M5: Feed API, Search, and Interactions" "m5,infra" \
  "## Why
Social interactions make the app sticky and feed the recommendation engine.

## What to build
- Like/unlike, bookmark/unbookmark, share tracking, read tracking
- Comment CRUD
- Interaction counts per article
- Rate limiting
- Events stored for recommendation engine

## Files to create
- src/api/interactions.py
- src/api/comments.py
- tests/test_interactions.py

## Acceptance Criteria
- [ ] Like/unlike toggles correctly
- [ ] Comments: create, list, delete own
- [ ] Read tracking with time spent
- [ ] Interaction counts updated atomically
- [ ] Rate limiting enforced
- [ ] All events stored for recommendations

## Branch: feature/issue-19-interactions
## Dependencies: Issues 4, 17"

create_issue 20 "Build trending and category APIs with breaking news support" \
  "M5: Feed API, Search, and Interactions" "m5,recommendation" \
  "## Why
Users want to discover what is happening right now. Trending, categories, and breaking news power the Explore page.

## What to build
- Trending API (velocity-based, last 1 hour)
- Category API (list, top per category)
- Breaking news detection (high velocity + recent)
- Explore endpoint (combined)
- Redis-cached velocity computation

## Files to create
- src/api/trending.py
- src/api/categories.py
- src/recommendation/trending.py
- tests/test_trending.py

## Acceptance Criteria
- [ ] Trending ranked by interaction velocity
- [ ] Category list with article counts
- [ ] Breaking news for high-velocity recent articles
- [ ] Explore combines breaking + trending + top per category
- [ ] Redis-cached, response < 100ms

## Branch: feature/issue-20-trending-categories
## Dependencies: Issues 17, 19"

# --- M6: Recommendation Engine ---

create_issue 21 "Build content-based recommender using topic and category similarity" \
  "M6: Recommendation Engine" "m6,recommendation" \
  "## Why
Content-based filtering is the foundation. Show users more of what they like.

## What to build
- User profile vector from engagement history
- Article scoring by cosine similarity
- Recency weighting (exponential decay, 3-day half-life)
- Category affinity tracker
- Cold start: use onboarding preferences

## Files to create
- src/recommendation/content_based.py
- src/recommendation/signals.py
- tests/test_content_based.py

## Acceptance Criteria
- [ ] User profile vector from engagement history
- [ ] Articles scored by similarity to profile
- [ ] Recent interactions weighted higher
- [ ] Cold start uses onboarding preferences
- [ ] Scoring 1000 articles < 1 second

## Branch: feature/issue-21-content-based
## Dependencies: Issue 19"

create_issue 22 "Build collaborative filtering with implicit feedback signals" \
  "M6: Recommendation Engine" "m6,recommendation" \
  "## Why
Collaborative filtering discovers unexpected connections that content-based cannot.

## What to build
- Implicit feedback matrix (users x articles)
- Signal weights: read=1, like=3, comment=5, share=7
- ALS via implicit library
- Retrain every 6 hours
- Cold start fallback to content-based

## Files to create
- src/recommendation/collaborative.py
- tests/test_collaborative.py

## Acceptance Criteria
- [ ] Interaction matrix from weighted signals
- [ ] ALS model trains successfully
- [ ] Retrains every 6 hours
- [ ] Different recommendations than content-based
- [ ] Cold start fallback for < 20 interactions
- [ ] Training on 10K interactions < 60 seconds

## Branch: feature/issue-22-collaborative-filtering
## Dependencies: Issue 21"

create_issue 23 "Build hybrid recommendation scorer with diversity injection" \
  "M6: Recommendation Engine" "m6,recommendation" \
  "## Why
Hybrid scoring blends all signals. Diversity injection prevents filter bubbles.

## What to build
- Hybrid scorer: content-based (0.4) + collaborative (0.35) + trending (0.25)
- Recency decay for older articles
- 20% diversity injection from underrepresented categories
- Filter bubble prevention

## Files to create
- src/recommendation/engine.py (expand)
- src/recommendation/diversity.py
- tests/test_recommendation_engine.py

## Acceptance Criteria
- [ ] Blends all signals with configurable weights
- [ ] Recency decay boosts recent articles
- [ ] 20% diversity picks from new categories
- [ ] Feed never > 50% single category
- [ ] Feed generation < 500ms per user

## Branch: feature/issue-23-hybrid-scorer
## Dependencies: Issues 21, 22, 20"

create_issue 24 "Build recommendation refresh scheduler and A/B test framework" \
  "M6: Recommendation Engine" "m6,recommendation,infra" \
  "## Why
Recommendations must stay fresh. A/B testing enables experimentation to improve engagement.

## What to build
- Refresh scheduler: recompute feeds every 30 minutes
- Redis-cached pre-computed feeds
- Cache invalidation on user interaction
- A/B test framework: experiment groups, variant assignment, metrics

## Files to create
- src/recommendation/ab_testing.py
- src/recommendation/metrics.py
- tests/test_ab_testing.py

## Acceptance Criteria
- [ ] Refresh runs every 30 minutes for active users
- [ ] Pre-computed feeds in Redis (top 50 per user per language)
- [ ] Cache invalidated on significant interaction
- [ ] A/B framework assigns consistent experiment groups
- [ ] Metrics tracked per variant: CTR, time spent
- [ ] 1000 user refresh < 5 minutes

## Branch: feature/issue-24-recommendation-scheduler
## Dependencies: Issue 23"

# --- M7: Mobile App ---

create_issue 25 "Build React Native app scaffold with Expo and navigation" \
  "M7: Mobile App" "m7,frontend" \
  "## Why
Mobile-first product. React Native gives native swipe gestures and app store distribution.

## What to build
- Expo project with TypeScript
- Tab navigator (Feed, Search, Bookmarks, Profile) + stack navigator
- Auth flow: Google OAuth -> onboarding -> main app
- API client with JWT management
- Language and theme context

## Files to create
- frontend/App.tsx, navigation/, screens/, api/, context/, theme/
- package.json, tsconfig.json, app.json

## Acceptance Criteria
- [ ] Builds on iOS simulator and Android emulator
- [ ] Tab + stack navigation works
- [ ] Google OAuth login flow works
- [ ] Onboarding shown on first login only
- [ ] API client attaches JWT, handles refresh
- [ ] Language context updates all content

## Branch: feature/issue-25-rn-scaffold
## Dependencies: Issue 4"

create_issue 26 "Build swipe feed screen with vertical swipe and infinite scroll" \
  "M7: Mobile App" "m7,frontend" \
  "## Why
The swipe feed IS the product. Instagram-like vertical swipe between full-screen snap cards.

## What to build
- Vertical swipe with FlatList pagingEnabled or react-native-pager-view
- SnapCard component (image, badge, summary, source, interaction bar)
- Infinite scroll, pull-to-refresh, loading skeleton
- Snap view tracking for recommendations

## Files to create
- frontend/screens/FeedScreen.tsx
- frontend/components/SnapCard.tsx, SwipeView.tsx, InteractionBar.tsx, SkeletonLoader.tsx
- frontend/hooks/useFeed.ts

## Acceptance Criteria
- [ ] Smooth vertical swipe at 60 FPS
- [ ] SnapCard shows image, badge, summary, source, time
- [ ] Infinite scroll loads next page
- [ ] Pull-to-refresh works
- [ ] Loading skeleton while content loads
- [ ] Snap views tracked for recommendations
- [ ] Works in all 5 languages

## Branch: feature/issue-26-swipe-feed
## Dependencies: Issues 17, 25"

create_issue 27 "Build search and explore screen with category chips and trending" \
  "M7: Mobile App" "m7,frontend" \
  "## Why
Explore screen drives discovery beyond the main feed. Instagram-style search + trending.

## What to build
- Search with real-time results and 300ms debounce
- Category chips (horizontal scroll)
- Trending grid (2 columns)
- Recent searches stored locally

## Files to create
- frontend/screens/SearchScreen.tsx
- frontend/components/SearchBar.tsx, CategoryChips.tsx, TrendingGrid.tsx, CompactSnapCard.tsx
- frontend/hooks/useSearch.ts

## Acceptance Criteria
- [ ] Search with 300ms debounce
- [ ] Compact result cards
- [ ] Category chips filter results
- [ ] Trending grid with top articles
- [ ] Recent searches stored locally
- [ ] Works in all 5 languages

## Branch: feature/issue-27-search-explore
## Dependencies: Issues 18, 20, 25"

create_issue 28 "Build social features UI with like animation and comment sheet" \
  "M7: Mobile App" "m7,frontend" \
  "## Why
Social features make the app sticky. Every interaction feeds the recommendation engine.

## What to build
- Like button with heart animation, double-tap to like
- Comment bottom sheet with input
- Native share sheet
- Bookmark with animation
- Haptic feedback

## Files to create
- frontend/components/LikeButton.tsx, CommentSheet.tsx, ShareButton.tsx, BookmarkButton.tsx
- frontend/api/interactions.ts
- frontend/hooks/useInteractions.ts

## Acceptance Criteria
- [ ] Like toggle with heart fill animation
- [ ] Double-tap snap triggers floating heart
- [ ] Comment sheet slides up with list + input
- [ ] Share opens native share sheet
- [ ] Bookmark toggles with animation
- [ ] Haptic feedback on like and bookmark

## Branch: feature/issue-28-social-features
## Dependencies: Issues 19, 26"

create_issue 29 "Build profile, settings, and onboarding screens" \
  "M7: Mobile App" "m7,frontend" \
  "## Why
Users need to manage preferences, which seed the recommendation engine.

## What to build
- Onboarding: welcome -> language -> categories -> done
- Profile: avatar, name, stats
- Settings: language, categories, notifications, logout
- Bookmarks list, reading history

## Files to create
- frontend/screens/OnboardingScreen.tsx, ProfileScreen.tsx, SettingsScreen.tsx, BookmarksScreen.tsx, HistoryScreen.tsx
- frontend/components/LanguagePicker.tsx, CategorySelector.tsx

## Acceptance Criteria
- [ ] 3-step onboarding (only on first login)
- [ ] Profile shows Google avatar, name, stats
- [ ] Language change updates feed immediately
- [ ] Category preferences editable (min 3)
- [ ] Logout clears JWT
- [ ] Bookmarks paginated with remove

## Branch: feature/issue-29-profile-settings
## Dependencies: Issues 25, 28"

# --- M8: Production Readiness ---

create_issue 30 "Build push notification system for breaking news and digests" \
  "M8: Production Readiness" "m8,infra" \
  "## Why
Push notifications bring users back. Breaking alerts and daily digests maintain engagement.

## What to build
- FCM integration for iOS and Android
- Breaking news: auto-trigger on high-velocity articles
- Daily digest: 8 AM IST, top 3 stories in user's language
- Notification preferences per type
- In-app notification history

## Files to create
- src/api/notifications.py
- src/utils/push_notifications.py
- frontend/utils/notifications.ts
- tests/test_notifications.py

## Acceptance Criteria
- [ ] FCM sends to iOS and Android
- [ ] Breaking news auto-triggers on velocity threshold
- [ ] Daily digest at 8 AM IST with top 3 stories
- [ ] Users can disable per notification type
- [ ] In-app history at GET /api/notifications
- [ ] Tapping opens relevant article

## Branch: feature/issue-30-push-notifications
## Dependencies: Issues 20, 29"

create_issue 31 "Build data cleanup scheduler with 2-week retention policy" \
  "M8: Production Readiness" "m8,infra" \
  "## Why
Mobile users rarely revisit old news. 2-week retention keeps the system lean and fast.

## What to build
- Daily cleanup at 3 AM IST
- Soft delete > 14 days, hard delete > 21 days
- Aggregate interactions before deleting raw events
- Orphan image cleanup, Meilisearch index cleanup
- Weekly VACUUM ANALYZE
- Dry run mode

## Files to create
- src/scheduler/cleanup.py
- tests/test_cleanup.py

## Acceptance Criteria
- [ ] Daily cleanup at 3 AM IST
- [ ] Articles > 14 days archived, > 21 days hard deleted
- [ ] Cascading removal of snaps, comments, images
- [ ] Interaction aggregates preserved
- [ ] Meilisearch index updated
- [ ] Weekly VACUUM ANALYZE
- [ ] Dry run mode available

## Branch: feature/issue-31-data-cleanup
## Dependencies: Issue 8"

create_issue 32 "Build admin monitoring dashboard for pipeline health" \
  "M8: Production Readiness" "m8,frontend,infra" \
  "## Why
Broken scrapers serve stale content. Dashboard provides real-time visibility.

## What to build
- Web-based admin dashboard
- Source health panel, pipeline throughput charts
- Content stats by language/category
- Error log, system health (DB, Redis, Meilisearch)
- Protected by admin role

## Files to create
- src/api/admin.py (expand)
- frontend/admin/ (React web dashboard)
- tests/test_admin_api.py

## Acceptance Criteria
- [ ] Source health with status, last scrape, error count
- [ ] Pipeline throughput chart (articles per hour)
- [ ] Content stats by language and category
- [ ] Error log (last 100 failures)
- [ ] System health (DB size, Redis memory, Meilisearch index)
- [ ] Admin role protection
- [ ] Auto-refresh every 60 seconds

## Branch: feature/issue-32-admin-dashboard
## Dependencies: Issue 8"

create_issue 33 "E2E testing, Redis caching, performance optimization, and deployment" \
  "M8: Production Readiness" "m8,infra" \
  "## Why
Final milestone. E2E tests verify the full pipeline. Caching and optimization for production. Docker deployment.

## What to build
- E2E test: scrape -> dedup -> summarize -> translate -> snap -> feed -> search
- Redis caching on feed, search, trending, categories
- Cache invalidation strategy
- Performance: feed < 200ms, search < 50ms
- Docker production build, deployment guide
- API rate limiting, CORS, health check

## Files to create
- tests/test_e2e.py
- src/utils/cache.py
- docker-compose.prod.yml
- docs/deployment.md

## Acceptance Criteria
- [ ] E2E test passes full pipeline
- [ ] Feed < 200ms, search < 50ms (cached)
- [ ] Redis caching with proper invalidation
- [ ] Rate limiting: 100 req/min per user
- [ ] Docker production build < 500MB
- [ ] Deployment guide for Railway/Render
- [ ] Health check at GET /health
- [ ] All tests pass

## Branch: feature/issue-33-deployment
## Dependencies: All previous issues"

echo ""
echo "All 33 issues created successfully!"
echo "Verify: gh issue list --repo $REPO --state open --limit 50"
