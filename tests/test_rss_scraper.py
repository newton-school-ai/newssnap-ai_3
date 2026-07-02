from unittest.mock import AsyncMock

import httpx
import pytest
from src.scrapers.article_parser import ParsedArticle
from src.scrapers.rss_scraper import RSSScraper
from src.scrapers.source_registry import SourceConfig
from src.scrapers.static_scraper import StaticScraper

SAMPLE_CONFIG = SourceConfig(
    name="Test RSS Source",
    base_url="https://example.com",
    scrape_type="rss",
    language="en",
    category_slug="national",
    feed_url="https://example.com/rss",
    title_selector="h1.title",
    body_selector="div.body",
    image_selector="meta[property='og:image']",
    rate_limit_seconds=0.01,
    category_mapping={"/sports/": "sports", "/world/": "international"},
)

LONG_PARAGRAPH = "This is a long article body that exceeds two hundred characters in length. " * 4

RSS2_FEED = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Test Feed</title>
<item>
<title>Full Story Title</title>
<link>https://example.com/national/full-story</link>
<pubDate>Mon, 23 Jun 2025 10:00:00 GMT</pubDate>
<description><![CDATA[<p>{LONG_PARAGRAPH}</p>]]></description>
</item>
<item>
<title>Short Story Title</title>
<link>https://example.com/sports/short-story</link>
<pubDate>Tue, 24 Jun 2025 12:00:00 GMT</pubDate>
<description>Short teaser only.</description>
</item>
</channel>
</rss>
"""

ATOM_FEED = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Test Atom Feed</title>
<entry>
<title>Atom Story Title</title>
<link href="https://example.com/world/atom-story" />
<updated>2025-06-23T10:00:00Z</updated>
<content type="html"><![CDATA[<p>{LONG_PARAGRAPH}</p>]]></content>
</entry>
</feed>
"""

RSS2_WITH_MEDIA = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
<title>Media Feed</title>
<item>
<title>Story With Image</title>
<link>https://example.com/national/story-with-image</link>
<pubDate>Mon, 23 Jun 2025 10:00:00 GMT</pubDate>
<description>Short teaser.</description>
<media:content url="https://example.com/images/story.jpg" type="image/jpeg" />
</item>
</channel>
</rss>
"""

NO_DATE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>No Date Feed</title>
<item>
<title>Undated Story</title>
<link>https://example.com/national/undated-story</link>
<description>Short teaser.</description>
</item>
</channel>
</rss>
"""


def _scraper_with_static(fetched_article: ParsedArticle | None = None) -> RSSScraper:
    static_scraper = StaticScraper()
    static_scraper.scrape_article = AsyncMock(return_value=fetched_article)
    return RSSScraper(static_scraper=static_scraper)


# --- Feed parsing: RSS 2.0 + Atom ---


def test_parse_rss2_feed():
    scraper = RSSScraper()
    feed = scraper.parse_feed(RSS2_FEED)
    assert feed.bozo == 0 or feed.bozo == False  # noqa: E712
    assert len(feed.entries) == 2
    assert feed.entries[0].title == "Full Story Title"


def test_parse_atom_feed():
    scraper = RSSScraper()
    feed = scraper.parse_feed(ATOM_FEED)
    assert len(feed.entries) == 1
    assert feed.entries[0].title == "Atom Story Title"
    assert feed.entries[0].link == "https://example.com/world/atom-story"


# --- Full-content vs link-only entries ---


@pytest.mark.asyncio
async def test_full_content_entry_skips_static_fetch():
    static_scraper = StaticScraper()
    static_scraper.scrape_article = AsyncMock()
    scraper = RSSScraper(static_scraper=static_scraper)

    feed = scraper.parse_feed(RSS2_FEED)
    articles = await scraper.parse_entries(feed, SAMPLE_CONFIG)

    full_story = next(a for a in articles if a.title == "Full Story Title")
    assert len(full_story.body) >= 200
    called_urls = [call.args[0] for call in static_scraper.scrape_article.call_args_list]
    assert full_story.source_url not in called_urls


@pytest.mark.asyncio
async def test_link_only_entry_fetches_via_static_scraper():
    fetched = ParsedArticle(
        title="Short Story Title",
        body="Full fetched body from the article page via httpx and BeautifulSoup.",
        image_url="https://example.com/img.jpg",
        source_url="https://example.com/sports/short-story",
        publish_time=None,
        category="sports",
    )
    scraper = _scraper_with_static(fetched_article=fetched)

    feed = scraper.parse_feed(RSS2_FEED)
    articles = await scraper.parse_entries(feed, SAMPLE_CONFIG)

    short_story = next(a for a in articles if a.title == "Short Story Title")
    scraper.static_scraper.scrape_article.assert_called_once()
    assert short_story.body == fetched.body
    assert short_story.image_url == "https://example.com/img.jpg"


# --- Normalization to ParsedArticle schema ---


@pytest.mark.asyncio
async def test_normalized_output_matches_article_schema():
    scraper = _scraper_with_static(fetched_article=None)
    feed = scraper.parse_feed(ATOM_FEED)
    articles = await scraper.parse_entries(feed, SAMPLE_CONFIG)

    assert len(articles) == 1
    article = articles[0]
    assert isinstance(article, ParsedArticle)
    assert article.title == "Atom Story Title"
    assert article.source_url == "https://example.com/world/atom-story"
    assert article.category == "international"
    assert article.publish_time is not None


# --- Date parsing: multiple formats ---


@pytest.mark.asyncio
async def test_date_parsing_rfc822_pubdate():
    scraper = _scraper_with_static()
    feed = scraper.parse_feed(RSS2_FEED)
    articles = await scraper.parse_entries(feed, SAMPLE_CONFIG)
    full_story = next(a for a in articles if a.title == "Full Story Title")
    assert full_story.publish_time is not None
    assert full_story.publish_time.year == 2025
    assert full_story.publish_time.month == 6
    assert full_story.publish_time.day == 23


@pytest.mark.asyncio
async def test_date_parsing_atom_iso8601():
    scraper = _scraper_with_static()
    feed = scraper.parse_feed(ATOM_FEED)
    articles = await scraper.parse_entries(feed, SAMPLE_CONFIG)
    assert articles[0].publish_time.year == 2025
    assert articles[0].publish_time.month == 6


@pytest.mark.asyncio
async def test_date_parsing_missing_date_returns_none():
    fetched = ParsedArticle(
        title="Undated Story",
        body="x" * 300,
        image_url=None,
        source_url="https://example.com/national/undated-story",
        publish_time=None,
        category="national",
    )
    scraper = _scraper_with_static(fetched_article=fetched)
    feed = scraper.parse_feed(NO_DATE_FEED)
    articles = await scraper.parse_entries(feed, SAMPLE_CONFIG)
    assert articles[0].publish_time is None


# --- Image extraction from media tags ---


@pytest.mark.asyncio
async def test_image_extracted_from_media_content():
    fetched = ParsedArticle(
        title="Story With Image",
        body="x" * 300,
        image_url=None,
        source_url="https://example.com/national/story-with-image",
        publish_time=None,
        category="national",
    )
    scraper = _scraper_with_static(fetched_article=fetched)
    feed = scraper.parse_feed(RSS2_WITH_MEDIA)
    articles = await scraper.parse_entries(feed, SAMPLE_CONFIG)
    assert articles[0].image_url == "https://example.com/images/story.jpg"


# --- scrape_source end-to-end ---


@pytest.mark.asyncio
async def test_scrape_source_fetches_and_parses():
    scraper = _scraper_with_static()
    scraper.fetch_feed_content = AsyncMock(return_value=RSS2_FEED.encode("utf-8"))

    articles = await scraper.scrape_source(SAMPLE_CONFIG)
    assert len(articles) == 2


@pytest.mark.asyncio
async def test_scrape_source_without_feed_url_returns_empty():
    config = SAMPLE_CONFIG.model_copy(update={"feed_url": None})
    scraper = RSSScraper()
    articles = await scraper.scrape_source(config)
    assert articles == []


@pytest.mark.asyncio
async def test_scrape_source_fetch_failure_returns_empty():
    scraper = RSSScraper()
    scraper.fetch_feed_content = AsyncMock(return_value=None)
    articles = await scraper.scrape_source(SAMPLE_CONFIG)
    assert articles == []


# --- Retry with exponential backoff on feed fetch ---


@pytest.mark.asyncio
async def test_fetch_feed_content_retries_on_failure(monkeypatch):
    scraper = RSSScraper()

    call_count = {"n": 0}

    class FakeResponse:
        def raise_for_status(self):
            return None

        content = b"<rss></rss>"

    async def fake_get(self, url, headers=None):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise httpx.ConnectError("boom", request=httpx.Request("GET", url))
        return FakeResponse()

    async def fast_sleep(_):
        return None

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr("asyncio.sleep", fast_sleep)

    content = await scraper.fetch_feed_content("https://example.com/rss")
    assert content == b"<rss></rss>"
    assert call_count["n"] == 3


@pytest.mark.asyncio
async def test_fetch_feed_content_gives_up_after_max_retries(monkeypatch):
    scraper = RSSScraper(max_retries=2)

    async def fake_get(self, url, headers=None):
        raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

    async def fast_sleep(_):
        return None

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr("asyncio.sleep", fast_sleep)

    content = await scraper.fetch_feed_content("https://example.com/rss")
    assert content is None


# --- StaticScraper ---


@pytest.mark.asyncio
async def test_static_scraper_parses_article():
    html = """
    <html><head><meta property="og:image" content="https://example.com/img.jpg"></head>
    <body><h1 class="title">Static Page Title</h1>
    <div class="body"><p>Paragraph one.</p><p>Paragraph two.</p></div></body></html>
    """
    scraper = StaticScraper()
    scraper.fetch_html = AsyncMock(return_value=html)

    article = await scraper.scrape_article("https://example.com/sports/page", SAMPLE_CONFIG)
    assert article is not None
    assert article.title == "Static Page Title"
    assert "Paragraph one." in article.body
    assert article.image_url == "https://example.com/img.jpg"
    assert article.category == "sports"


@pytest.mark.asyncio
async def test_static_scraper_returns_none_when_fetch_fails():
    scraper = StaticScraper()
    scraper.fetch_html = AsyncMock(return_value=None)
    article = await scraper.scrape_article("https://example.com/a", SAMPLE_CONFIG)
    assert article is None


@pytest.mark.asyncio
async def test_static_scraper_returns_none_without_title():
    html = "<html><body><div class='body'>No title here</div></body></html>"
    scraper = StaticScraper()
    scraper.fetch_html = AsyncMock(return_value=html)
    article = await scraper.scrape_article("https://example.com/a", SAMPLE_CONFIG)
    assert article is None
