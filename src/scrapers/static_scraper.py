from __future__ import annotations

import asyncio
import logging

import httpx
from bs4 import BeautifulSoup

from src.scrapers.article_parser import (
    ParsedArticle,
    extract_article_body,
    extract_meta_content,
    map_category,
)
from src.scrapers.browser_pool import random_user_agent
from src.scrapers.source_registry import SourceConfig
from src.utils.time_utils import parse_datetime

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 15.0


class StaticScraper:
    """Fetches static (non-JS-rendered) pages via httpx + BeautifulSoup."""

    def __init__(self, max_retries: int = DEFAULT_MAX_RETRIES, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self.max_retries = max_retries
        self.timeout = timeout

    async def fetch_html(self, url: str, headers: dict[str, str] | None = None) -> str | None:
        request_headers = {"User-Agent": random_user_agent()}
        if headers:
            request_headers.update(headers)

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.get(url, headers=request_headers)
                    response.raise_for_status()
                    return response.text
                except httpx.HTTPError as exc:
                    last_error = exc
                    backoff = 2**attempt
                    logger.warning("Failed to fetch %s (attempt %d/%d): %s", url, attempt + 1, self.max_retries, exc)
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(backoff)

        logger.error("Giving up on %s after %d attempts: %s", url, self.max_retries, last_error)
        return None

    async def scrape_article(self, url: str, config: SourceConfig) -> ParsedArticle | None:
        html = await self.fetch_html(url, headers=config.custom_headers)
        if html is None:
            return None
        return self._parse_article(html, url, config)

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
