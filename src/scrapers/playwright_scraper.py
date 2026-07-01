from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.scrapers.article_parser import (
    ParsedArticle,
    extract_article_body,
    extract_links,
    extract_meta_content,
    map_category,
)
from src.scrapers.browser_pool import BrowserPool, random_user_agent
from src.scrapers.source_registry import SourceConfig
from src.utils.time_utils import parse_datetime

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_NAV_TIMEOUT_MS = 30000


class PlaywrightScraper:
    """Scrapes JS-rendered news sites using a shared Playwright browser pool."""

    def __init__(self, pool: BrowserPool | None = None, max_retries: int = DEFAULT_MAX_RETRIES):
        self.pool = pool or BrowserPool()
        self.max_retries = max_retries
        self._last_request_at: dict[str, float] = {}

    async def _respect_rate_limit(self, url: str, rate_limit_seconds: float) -> None:
        domain = urlparse(url).netloc
        last_time = self._last_request_at.get(domain)
        if last_time is not None:
            elapsed = time.monotonic() - last_time
            wait = rate_limit_seconds - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
        self._last_request_at[domain] = time.monotonic()

    async def _goto_with_retry(self, page: Page, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                await page.goto(url, timeout=DEFAULT_NAV_TIMEOUT_MS, wait_until="domcontentloaded")
                return await page.content()
            except (PlaywrightTimeoutError, Exception) as exc:  # noqa: BLE001
                last_error = exc
                backoff = 2**attempt
                logger.warning("Failed to load %s (attempt %d/%d): %s", url, attempt + 1, self.max_retries, exc)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(backoff)
        raise RuntimeError(f"Failed to load {url} after {self.max_retries} attempts") from last_error

    async def scrape_article_list(self, config: SourceConfig) -> list[str]:
        if not config.article_list_url or not config.article_link_selector:
            return []

        await self._respect_rate_limit(config.article_list_url, config.rate_limit_seconds)

        browser, context, page = await self.pool.new_page(user_agent=random_user_agent())
        try:
            html = await self._goto_with_retry(page, config.article_list_url)
            return extract_links(html, config.base_url, config.article_link_selector)
        finally:
            await self.pool.release_context(browser, context)

    async def scrape_article(self, url: str, config: SourceConfig) -> ParsedArticle | None:
        await self._respect_rate_limit(url, config.rate_limit_seconds)

        browser, context, page = await self.pool.new_page(user_agent=random_user_agent())
        try:
            html = await self._goto_with_retry(page, url)
            return self._parse_article(html, url, config)
        except RuntimeError:
            logger.exception("Failed to scrape article: %s", url)
            return None
        finally:
            await self.pool.release_context(browser, context)

    def _parse_article(self, html: str, url: str, config: SourceConfig) -> ParsedArticle | None:
        soup = BeautifulSoup(html, "html.parser")

        title = ""
        if config.title_selector:
            title_el = soup.select_one(config.title_selector)
            if title_el:
                title = title_el.get_text(strip=True)

        if not title:
            return None

        body = extract_article_body(soup, config.body_selector) if config.body_selector else ""
        image_url = extract_meta_content(soup, config.image_selector) if config.image_selector else None
        publish_time_raw = extract_meta_content(soup, config.date_selector) if config.date_selector else None
        category = map_category(url, config.category_mapping, config.category_slug)

        return ParsedArticle(
            title=title,
            body=body,
            image_url=image_url,
            source_url=url,
            publish_time=parse_datetime(publish_time_raw),
            category=category,
        )

    async def scrape_source(self, config: SourceConfig, limit: int = 10) -> list[ParsedArticle]:
        article_urls = await self.scrape_article_list(config)
        articles: list[ParsedArticle] = []

        for url in article_urls[:limit]:
            article = await self.scrape_article(url, config)
            if article is not None:
                articles.append(article)

        return articles
