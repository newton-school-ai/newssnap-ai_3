from __future__ import annotations

import asyncio
import logging
from calendar import timegm
from datetime import datetime, timezone

import feedparser
import httpx
from bs4 import BeautifulSoup

from src.scrapers.article_parser import ParsedArticle, map_category
from src.scrapers.browser_pool import random_user_agent
from src.scrapers.source_registry import SourceConfig
from src.scrapers.static_scraper import StaticScraper
from src.utils.time_utils import parse_datetime

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 15.0
MIN_FULL_CONTENT_LENGTH = 200


class RSSScraper:
    """Parses RSS 2.0 / Atom feeds and normalizes entries into the shared ParsedArticle schema."""
    def __init__(
        self,
        static_scraper: StaticScraper | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.static_scraper = static_scraper or StaticScraper()
        self.max_retries = max_retries
        self.timeout = timeout

    async def fetch_feed_content(self, feed_url: str, headers: dict[str, str] | None = None) -> bytes | None:
        request_headers = {"User-Agent": random_user_agent()}
        if headers:
            request_headers.update(headers)

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.get(feed_url, headers=request_headers)
                    response.raise_for_status()
                    return response.content
                except httpx.HTTPError as exc:
                    last_error = exc
                    backoff = 2**attempt
                    logger.warning(
                        "Failed to fetch feed %s (attempt %d/%d): %s", feed_url, attempt + 1, self.max_retries, exc
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(backoff)

        logger.error("Giving up on feed %s after %d attempts: %s", feed_url, self.max_retries, last_error)
        return None

    def parse_feed(self, content: bytes | str):
        return feedparser.parse(content)

    def _entry_published_at(self, entry) -> datetime | None:
        for key in ("published_parsed", "updated_parsed"):
            struct = entry.get(key)
            if struct:
                return datetime.fromtimestamp(timegm(struct), tz=timezone.utc)

        for key in ("published", "updated", "pubDate"):
            raw = entry.get(key)
            if raw:
                parsed = parse_datetime(raw)
                if parsed:
                    return parsed

        return None

    def _entry_content(self, entry) -> str:
        content_list = entry.get("content")
        if content_list:
            return content_list[0].get("value", "")
        return entry.get("summary", "") or entry.get("description", "")

    def _strip_html(self, html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n", strip=True)

    def _entry_image(self, entry) -> str | None:
        media_content = entry.get("media_content")
        if media_content:
            url = media_content[0].get("url")
            if url:
                return url

        media_thumbnail = entry.get("media_thumbnail")
        if media_thumbnail:
            url = media_thumbnail[0].get("url")
            if url:
                return url

        for link in entry.get("links", []):
            if link.get("type", "").startswith("image"):
                return link.get("href")

        for enclosure in entry.get("enclosures", []):
            if enclosure.get("type", "").startswith("image"):
                return enclosure.get("href")

        return None

    async def parse_entries(self, feed, config: SourceConfig, limit: int = 30) -> list[ParsedArticle]:
        articles: list[ParsedArticle] = []

        for entry in feed.entries[:limit]:
            url = entry.get("link")
            if not url:
                continue

            title = entry.get("title", "").strip()
            if not title:
                continue

            body = self._strip_html(self._entry_content(entry))
            publish_time = self._entry_published_at(entry)
            image_url = self._entry_image(entry)
            category = map_category(url, config.category_mapping, config.category_slug)

            if len(body) < MIN_FULL_CONTENT_LENGTH:
                fetched = await self.static_scraper.scrape_article(url, config)
                if fetched is not None:
                    body = fetched.body or body
                    image_url = image_url or fetched.image_url
                    publish_time = publish_time or fetched.publish_time

            articles.append(
                ParsedArticle(
                    title=title,
                    body=body,
                    image_url=image_url,
                    source_url=url,
                    publish_time=publish_time,
                    category=category,
                )
            )

        return articles

    async def scrape_source(self, config: SourceConfig, limit: int = 30) -> list[ParsedArticle]:
        if not config.feed_url:
            return []

        content = await self.fetch_feed_content(config.feed_url, headers=config.custom_headers)
        if content is None:
            return []

        feed = self.parse_feed(content)
        return await self.parse_entries(feed, config, limit=limit)
