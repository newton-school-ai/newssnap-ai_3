from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.scheduler.scrape_pipeline import ScrapePipeline
from src.scrapers.source_registry import SourceConfig, SourceRegistry

logger = logging.getLogger(__name__)

SCRAPE_INTERVAL_SECONDS = 600
UNHEALTHY_THRESHOLD = 5


class ScrapeScheduler:
    def __init__(self, pipeline: ScrapePipeline, registry: SourceRegistry):
        self.pipeline = pipeline
        self.registry = registry
        self._scheduler = AsyncIOScheduler()
        self._consecutive_failures: dict[str, int] = {}

    def start(self) -> None:
        self._scheduler.add_job(
            self._run_all_sources,
            "interval",
            seconds=SCRAPE_INTERVAL_SECONDS,
            id="scrape_all_sources",
            max_instances=1,
        )
        self._scheduler.start()
        logger.info("Scrape scheduler started (interval=%ds)", SCRAPE_INTERVAL_SECONDS)

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scrape scheduler stopped")

    async def _run_all_sources(self) -> None:
        sources = self.registry.get_active_sources()
        if not sources:
            logger.info("No active sources to scrape")
            return

        delay_step = SCRAPE_INTERVAL_SECONDS / len(sources)
        logger.info("Scheduling %d sources with %.1fs stagger", len(sources), delay_step)

        tasks = [
            self._run_source_with_delay(config, i * delay_step)
            for i, config in enumerate(sources)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_source_with_delay(self, config: SourceConfig, delay: float) -> None:
        if delay > 0:
            await asyncio.sleep(delay)
        await self._run_source_safe(config)

    async def _run_source_safe(self, config: SourceConfig) -> None:
        try:
            count = await self.pipeline.run_source(config)
            self.registry.record_success(config.name)
            self._consecutive_failures[config.name] = 0
            logger.info("Scraped %d new articles from '%s'", count, config.name)
        except Exception as exc:
            failures = self._consecutive_failures.get(config.name, 0) + 1
            self._consecutive_failures[config.name] = failures
            self.registry.record_error(config.name, str(exc), unhealthy_threshold=UNHEALTHY_THRESHOLD)
            logger.error(
                "Error scraping '%s' (consecutive failure %d/%d): %s",
                config.name,
                failures,
                UNHEALTHY_THRESHOLD,
                exc,
            )

    def get_consecutive_failures(self, name: str) -> int:
        return self._consecutive_failures.get(name, 0)

    @property
    def is_running(self) -> bool:
        return self._scheduler.running
