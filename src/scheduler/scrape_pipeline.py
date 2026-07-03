from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.article import Article
from src.scrapers.article_parser import ParsedArticle
from src.scrapers.rss_scraper import RSSScraper
from src.scrapers.source_registry import SourceConfig, SourceRegistry
from src.scrapers.static_scraper import StaticScraper

logger = logging.getLogger(__name__)


class ScrapePipeline:
    def __init__(self, registry: SourceRegistry, session_factory: Callable[[], Session]):
        self.registry = registry
        self.session_factory = session_factory

    async def run_source(self, config: SourceConfig) -> int:
        articles = await self._fetch_articles(config)
        if not articles:
            return 0
        return self._store_articles(articles, config)

    async def _fetch_articles(self, config: SourceConfig) -> list[ParsedArticle]:
        if config.scrape_type == "rss":
            return await RSSScraper().scrape_source(config)

        if config.scrape_type == "playwright":
            from src.scrapers.browser_pool import BrowserPool
            from src.scrapers.playwright_scraper import PlaywrightScraper

            pool = BrowserPool()
            await pool.start()
            try:
                return await PlaywrightScraper(pool=pool).scrape_source(config)
            finally:
                await pool.stop()

        return await StaticScraper().scrape_source(config)

    def _store_articles(self, articles: list[ParsedArticle], config: SourceConfig) -> int:
        db = self.session_factory()
        try:
            stored = 0
            for article in articles:
                if db.scalar(select(Article).where(Article.url == article.source_url)):
                    continue
                db.add(
                    Article(
                        url=article.source_url,
                        title=article.title,
                        content=article.body,
                        language=config.language,
                        category_slug=article.category,
                        image_url=article.image_url,
                        publish_time=article.publish_time,
                    )
                )
                stored += 1
            db.commit()
            return stored
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
