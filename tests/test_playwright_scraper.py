import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.scrapers.article_parser import extract_links, map_category
from src.scrapers.browser_pool import USER_AGENTS, random_user_agent
from src.scrapers.playwright_scraper import PlaywrightScraper
from src.scrapers.source_registry import SourceConfig

SAMPLE_CONFIG = SourceConfig(
    name="Test Source",
    base_url="https://example.com",
    scrape_type="playwright",
    language="en",
    category_slug="national",
    article_list_url="https://example.com/news",
    article_link_selector="a.article-link",
    title_selector="h1.title",
    body_selector="div.body",
    image_selector="meta[property='og:image']",
    rate_limit_seconds=0.01,
    category_mapping={"/sports/": "sports"},
)

SAMPLE_LIST_HTML = """
<html><body>
<a class="article-link" href="/sports/article-1">Story 1</a>
<a class="article-link" href="/national/article-2">Story 2</a>
</body></html>
"""

SAMPLE_ARTICLE_HTML = """
<html><head>
<meta property="og:image" content="https://example.com/img.jpg">
</head><body>
<h1 class="title">Breaking News Headline</h1>
<div class="body"><p>First paragraph.</p><p>Second paragraph.</p></div>
</body></html>
"""


def _make_mock_pool(html_by_call):
    pool = MagicMock()
    page = AsyncMock()
    page.content = AsyncMock(side_effect=html_by_call)
    page.goto = AsyncMock(return_value=None)

    browser = MagicMock()
    context = MagicMock()

    pool.new_page = AsyncMock(return_value=(browser, context, page))
    pool.release_context = AsyncMock(return_value=None)
    return pool, page


# --- User agent rotation ---


def test_user_agent_pool_has_10_plus():
    assert len(USER_AGENTS) >= 10


def test_random_user_agent_returns_valid():
    ua = random_user_agent()
    assert ua in USER_AGENTS


# --- Link extraction ---


def test_extract_links():
    links = extract_links(SAMPLE_LIST_HTML, "https://example.com", "a.article-link")
    assert len(links) == 2
    assert "https://example.com/sports/article-1" in links
    assert "https://example.com/national/article-2" in links


def test_map_category_matches_fragment():
    category = map_category("https://example.com/sports/article-1", {"/sports/": "sports"}, "national")
    assert category == "sports"


def test_map_category_falls_back_to_default():
    category = map_category("https://example.com/other/article", {"/sports/": "sports"}, "national")
    assert category == "national"


# --- Rate limiting ---


@pytest.mark.asyncio
async def test_rate_limit_enforces_delay():
    scraper = PlaywrightScraper(pool=MagicMock())
    url = "https://example.com/a"

    start = asyncio.get_event_loop().time()
    await scraper._respect_rate_limit(url, 0.1)
    await scraper._respect_rate_limit(url, 0.1)
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed >= 0.09


@pytest.mark.asyncio
async def test_rate_limit_per_domain_independent():
    scraper = PlaywrightScraper(pool=MagicMock())
    await scraper._respect_rate_limit("https://a.com/x", 5.0)
    start = asyncio.get_event_loop().time()
    await scraper._respect_rate_limit("https://b.com/y", 5.0)
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 1.0


# --- Article scraping ---


@pytest.mark.asyncio
async def test_scrape_article_list():
    pool, _ = _make_mock_pool([SAMPLE_LIST_HTML])
    scraper = PlaywrightScraper(pool=pool)
    urls = await scraper.scrape_article_list(SAMPLE_CONFIG)
    assert len(urls) == 2


@pytest.mark.asyncio
async def test_scrape_article_parses_fields():
    pool, _ = _make_mock_pool([SAMPLE_ARTICLE_HTML])
    scraper = PlaywrightScraper(pool=pool)
    article = await scraper.scrape_article("https://example.com/sports/article-1", SAMPLE_CONFIG)

    assert article is not None
    assert article.title == "Breaking News Headline"
    assert "First paragraph." in article.body
    assert article.image_url == "https://example.com/img.jpg"
    assert article.category == "sports"
    assert article.source_url == "https://example.com/sports/article-1"


@pytest.mark.asyncio
async def test_scrape_article_without_title_returns_none():
    html_no_title = "<html><body><div class='body'>No title here</div></body></html>"
    pool, _ = _make_mock_pool([html_no_title])
    scraper = PlaywrightScraper(pool=pool)
    article = await scraper.scrape_article("https://example.com/a", SAMPLE_CONFIG)
    assert article is None


@pytest.mark.asyncio
async def test_scrape_source_combines_list_and_articles():
    pool, _ = _make_mock_pool([SAMPLE_LIST_HTML, SAMPLE_ARTICLE_HTML, SAMPLE_ARTICLE_HTML])
    scraper = PlaywrightScraper(pool=pool)
    articles = await scraper.scrape_source(SAMPLE_CONFIG, limit=10)
    assert len(articles) == 2


# --- Retry with exponential backoff ---


@pytest.mark.asyncio
async def test_goto_retries_on_failure_then_succeeds():
    page = AsyncMock()
    page.goto = AsyncMock(side_effect=[Exception("timeout"), Exception("timeout"), None])
    page.content = AsyncMock(return_value=SAMPLE_ARTICLE_HTML)

    scraper = PlaywrightScraper(pool=MagicMock(), max_retries=3)
    scraper._respect_rate_limit = AsyncMock()

    async def fast_sleep(_):
        return None

    original_sleep = asyncio.sleep
    asyncio.sleep = fast_sleep
    try:
        html = await scraper._goto_with_retry(page, "https://example.com/a")
    finally:
        asyncio.sleep = original_sleep

    assert html == SAMPLE_ARTICLE_HTML
    assert page.goto.call_count == 3


@pytest.mark.asyncio
async def test_goto_raises_after_max_retries():
    page = AsyncMock()
    page.goto = AsyncMock(side_effect=Exception("always fails"))

    scraper = PlaywrightScraper(pool=MagicMock(), max_retries=3)

    async def fast_sleep(_):
        return None

    original_sleep = asyncio.sleep
    asyncio.sleep = fast_sleep
    try:
        with pytest.raises(RuntimeError):
            await scraper._goto_with_retry(page, "https://example.com/a")
    finally:
        asyncio.sleep = original_sleep

    assert page.goto.call_count == 3


# --- Browser pool reuse ---


def test_browser_pool_initial_state():
    from src.scrapers.browser_pool import BrowserPool

    pool = BrowserPool(pool_size=2)
    assert pool.pool_size == 2
    assert pool._started is False
