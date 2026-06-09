# Milestones - NewsSnap AI

## M1: Project Scaffold, DB, and Auth (Week 1)

### Key Output
DB schema with all tables, Google OAuth login, news source config system, CI/Docker setup.

### Acceptance Criteria
- Docker compose starts all services (backend, PostgreSQL, Redis, Meilisearch)
- CI runs lint + tests on every PR
- All database tables created with proper indexes and relationships
- Google OAuth flow works end-to-end (login -> JWT -> protected routes)
- At least 10 news source configs created
- Seed data populates sources and categories

### Defense Questions
- Walk through the database schema. Why did you choose these tables and relationships?
- How does JWT token refresh work? What happens when the access token expires?
- How does the source config system work? How would you add a new news source?
- Explain the Docker setup. What does each service do?
- How are database indexes chosen? Which queries do they optimize?

---

## M2: News Scraping Pipeline (Week 2)

### Key Output
Working scrapers for JS-rendered sites (Playwright), RSS feeds, and static pages. Scheduler runs every 10 minutes.

### Acceptance Criteria
- Playwright scraper extracts articles from 5+ JS-rendered news sites
- RSS scraper parses feeds from 3+ sources
- Article parser produces clean text with no HTML/ads
- Scheduler runs every 10 minutes, stores articles in database
- Source health tracked (success/error counts)
- Failed scrapes retry with exponential backoff

### Defense Questions
- Why Playwright instead of requests + BeautifulSoup for some sites?
- How does the scraper handle rate limiting and avoid getting blocked?
- What happens when a source is down? How does the health system work?
- Walk through the article parsing pipeline. How do you handle noisy HTML?
- How is the 10-minute schedule distributed across sources?

---

## M3: AI Content Pipeline (Week 3)

### Key Output
Dedup catches duplicate articles, stories are clustered, summaries are crisp 60-80 word paragraphs, spam/clickbait filtered.

### Acceptance Criteria
- Dedup agent catches paraphrased duplicates (cosine similarity > 0.85)
- Story clustering groups related articles from different sources
- Summaries are 60-80 words, factual, engaging
- Quality filter rejects clickbait and incomplete articles
- Pipeline processes 100 articles in < 2 minutes

### Defense Questions
- Explain how embedding-based deduplication works. Why cosine similarity?
- What is DBSCAN? Why use it for story clustering instead of K-means?
- How is the summarizer prompt engineered? Show category-specific examples.
- What makes an article "clickbait"? How does the quality filter detect it?
- How do you handle the case where dedup threshold is too aggressive or too lenient?

---

## M4: Translation and Snap Generation (Week 4)

### Key Output
Summaries translated to all 5 languages, visual snaps generated with white background layout, category-specific templates.

### Acceptance Criteria
- Translator produces natural translations in all 5 languages
- Snap images are 1080x1920 with clean white background layout
- Lead images extracted and resized to 16:9
- Category placeholders used when no image found
- At least 6 snap templates (general, finance, sports, entertainment, politics, technology)

### Defense Questions
- How do you ensure translations are natural, not literal word-by-word?
- What is the back-translation quality check? How does it work?
- Walk through the snap composition pipeline. How is text wrapped and sized?
- How do you handle articles with no lead image?
- What is IndicTrans2 and when does the fallback trigger?

---

## M5: Feed API, Search, and Interactions (Week 5)

### Key Output
Personalized feed API, multi-language search, like/comment/share/bookmark system, trending/breaking news.

### Acceptance Criteria
- Feed API returns personalized snaps with cursor-based pagination
- Meilisearch search works across all 5 languages with typo tolerance
- Like, comment, share, bookmark all work correctly
- Trending API returns high-velocity articles
- Breaking news detection works for high-velocity recent articles
- Feed response time < 200ms

### Defense Questions
- Why cursor-based pagination instead of offset-based?
- How does Meilisearch handle multi-language search?
- How are interaction counts updated atomically? What prevents race conditions?
- Explain the trending velocity calculation. What time window is used?
- How do you define "breaking news"? What thresholds are used?

---

## M6: Recommendation Engine (Week 6)

### Key Output
Content-based + collaborative filtering + trending blend with diversity injection. Feeds are personalized and diverse.

### Acceptance Criteria
- Content-based recommender scores articles by category similarity to user history
- Collaborative filtering discovers cross-category recommendations
- Hybrid scorer blends all signals with configurable weights
- 20% diversity injection prevents filter bubbles
- Recommendations refresh every 30 minutes, cached in Redis
- A/B test framework assigns users to experiment groups

### Defense Questions
- Explain the difference between content-based and collaborative filtering.
- What is ALS (Alternating Least Squares)? How does it work for implicit feedback?
- Why inject diversity? What is a filter bubble?
- How do you handle cold start (new user with no history)?
- Walk through the A/B test framework. How are users assigned to variants?

---

## M7: Mobile App (Week 7)

### Key Output
React Native app with swipe feed, search/explore, social features (like, comment, share), profile/settings.

### Acceptance Criteria
- Swipe feed: smooth vertical swipe between full-screen snap cards
- Search: text search with real-time results and category chips
- Like animation, comment bottom sheet, native share
- Profile shows user stats, settings for language/categories/notifications
- Onboarding flow for new users
- App works on both iOS and Android

### Defense Questions
- Why React Native instead of Flutter or native?
- How does the swipe gesture work? What library handles it?
- How is JWT token managed in the mobile app?
- Walk through the state management approach. Why this library?
- How do you handle offline or slow network conditions?

---

## M8: Production Readiness (Week 8)

### Key Output
Push notifications, 2-week data cleanup, admin dashboard, E2E tests, Docker deployment. App is production-ready.

### Acceptance Criteria
- Push notifications work for breaking news and daily digest
- 2-week cleanup removes old articles, snaps, and orphaned data
- Admin dashboard shows source health, pipeline throughput, errors
- E2E test passes full pipeline: scrape -> feed
- All API endpoints cached in Redis, < 200ms response
- Docker production build deploys to Railway/Render
- All tests pass (unit + integration + E2E)

### Defense Questions
- How does FCM push notification work? What triggers a breaking news alert?
- Walk through the cleanup process. What is preserved vs deleted?
- What metrics does the admin dashboard show? Why these?
- How do you ensure the E2E test covers all pipeline stages?
- Explain the Redis caching strategy. When is cache invalidated?

---

NST Engineering - NewsSnap AI | Summer Profile Building Drive 2026
