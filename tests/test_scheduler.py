from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.admin import router as admin_router
from src.api.middleware import CurrentUser, get_current_user, require_admin
from src.scheduler.jobs import SCRAPE_INTERVAL_SECONDS, UNHEALTHY_THRESHOLD, ScrapeScheduler
from src.scheduler.scrape_pipeline import ScrapePipeline
from src.scrapers.article_parser import ParsedArticle
from src.scrapers.source_registry import SourceConfig, SourceHealth, SourceRegistry

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_ADMIN_USER = CurrentUser(user_id="admin-1", role="admin")


def _make_config(name: str = "Test Source", scrape_type: str = "rss") -> SourceConfig:
    return SourceConfig(
        name=name,
        base_url="https://example.com",
        scrape_type=scrape_type,
        language="en",
        category_slug="national",
        feed_url="https://example.com/rss" if scrape_type == "rss" else None,
        article_list_url="https://example.com/news" if scrape_type == "playwright" else None,
        article_link_selector="a.link" if scrape_type == "playwright" else None,
        rate_limit_seconds=0.01,
    )


def _make_article(url: str = "https://example.com/article-1") -> ParsedArticle:
    return ParsedArticle(
        title="Breaking News",
        body="Article body text with plenty of words to fill the content field.",
        image_url="https://example.com/img.jpg",
        source_url=url,
        publish_time=datetime(2025, 6, 23, 10, 0, 0, tzinfo=timezone.utc),
        category="national",
    )


def _make_registry(*configs: SourceConfig) -> SourceRegistry:
    reg = SourceRegistry.__new__(SourceRegistry)
    reg._configs_dir = None
    reg._sources = {}
    reg._health = {}
    for cfg in configs:
        key = SourceRegistry._make_key(cfg.name)
        reg._sources[key] = cfg
        reg._health[key] = SourceHealth()
    return reg


def _make_session(existing_article=None):
    session = MagicMock()
    session.scalar.return_value = existing_article
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


# ---------------------------------------------------------------------------
# ScrapePipeline: article storage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_stores_new_articles():
    config = _make_config("RSS Source", "rss")
    articles = [_make_article("https://example.com/a1"), _make_article("https://example.com/a2")]

    session = _make_session(existing_article=None)
    factory = MagicMock(return_value=session)

    registry = _make_registry(config)
    pipeline = ScrapePipeline(registry, factory)

    with patch("src.scheduler.scrape_pipeline.RSSScraper") as mock_cls:
        mock_cls.return_value.scrape_source = AsyncMock(return_value=articles)
        count = await pipeline.run_source(config)

    assert count == 2
    assert session.add.call_count == 2
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_skips_duplicate_urls():
    config = _make_config()
    articles = [_make_article()]

    session = _make_session(existing_article=MagicMock())
    factory = MagicMock(return_value=session)

    registry = _make_registry(config)
    pipeline = ScrapePipeline(registry, factory)

    with patch("src.scheduler.scrape_pipeline.RSSScraper") as mock_cls:
        mock_cls.return_value.scrape_source = AsyncMock(return_value=articles)
        count = await pipeline.run_source(config)

    assert count == 0
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_returns_zero_when_no_articles():
    config = _make_config()
    session = _make_session()
    registry = _make_registry(config)
    pipeline = ScrapePipeline(registry, MagicMock(return_value=session))

    with patch("src.scheduler.scrape_pipeline.RSSScraper") as mock_cls:
        mock_cls.return_value.scrape_source = AsyncMock(return_value=[])
        count = await pipeline.run_source(config)

    assert count == 0
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_rolls_back_on_db_error():
    config = _make_config()
    articles = [_make_article()]

    session = _make_session(existing_article=None)
    session.commit.side_effect = Exception("DB error")
    factory = MagicMock(return_value=session)

    registry = _make_registry(config)
    pipeline = ScrapePipeline(registry, factory)

    with patch("src.scheduler.scrape_pipeline.RSSScraper") as mock_cls:
        mock_cls.return_value.scrape_source = AsyncMock(return_value=articles)
        with pytest.raises(Exception, match="DB error"):
            await pipeline.run_source(config)

    session.rollback.assert_called_once()
    session.close.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_uses_rss_scraper_for_rss_sources():
    config = _make_config(scrape_type="rss")
    session = _make_session()
    pipeline = ScrapePipeline(_make_registry(config), MagicMock(return_value=session))

    with patch("src.scheduler.scrape_pipeline.RSSScraper") as mock_rss, patch(
        "src.scheduler.scrape_pipeline.StaticScraper"
    ) as mock_static:
        mock_rss.return_value.scrape_source = AsyncMock(return_value=[])
        await pipeline.run_source(config)

    mock_rss.assert_called_once()
    mock_static.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_uses_static_scraper_for_api_sources():
    config = _make_config(scrape_type="static")
    session = _make_session()
    pipeline = ScrapePipeline(_make_registry(config), MagicMock(return_value=session))

    with patch("src.scheduler.scrape_pipeline.StaticScraper") as mock_static, patch(
        "src.scheduler.scrape_pipeline.RSSScraper"
    ) as mock_rss:
        mock_static.return_value.scrape_source = AsyncMock(return_value=[])
        await pipeline.run_source(config)

    mock_static.assert_called_once()
    mock_rss.assert_not_called()


# ---------------------------------------------------------------------------
# ScrapeScheduler: per-source error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_records_success():
    config = _make_config()
    registry = _make_registry(config)
    pipeline = MagicMock()
    pipeline.run_source = AsyncMock(return_value=3)

    scheduler = ScrapeScheduler(pipeline, registry)
    await scheduler._run_source_safe(config)

    health = registry.get_health(config.name)
    assert health.success_count == 1
    assert health.is_healthy is True
    assert scheduler.get_consecutive_failures(config.name) == 0


@pytest.mark.asyncio
async def test_scheduler_records_failure():
    config = _make_config()
    registry = _make_registry(config)
    pipeline = MagicMock()
    pipeline.run_source = AsyncMock(side_effect=Exception("timeout"))

    scheduler = ScrapeScheduler(pipeline, registry)
    await scheduler._run_source_safe(config)

    health = registry.get_health(config.name)
    assert health.error_count == 1
    assert scheduler.get_consecutive_failures(config.name) == 1


@pytest.mark.asyncio
async def test_scheduler_marks_unhealthy_after_threshold():
    config = _make_config()
    registry = _make_registry(config)
    pipeline = MagicMock()
    pipeline.run_source = AsyncMock(side_effect=Exception("connection refused"))

    scheduler = ScrapeScheduler(pipeline, registry)
    for _ in range(UNHEALTHY_THRESHOLD):
        await scheduler._run_source_safe(config)

    health = registry.get_health(config.name)
    assert health.is_healthy is False
    assert scheduler.get_consecutive_failures(config.name) == UNHEALTHY_THRESHOLD


@pytest.mark.asyncio
async def test_scheduler_resets_failures_on_success():
    config = _make_config()
    registry = _make_registry(config)
    pipeline = MagicMock()
    pipeline.run_source = AsyncMock(side_effect=[Exception("fail"), Exception("fail"), 5])

    scheduler = ScrapeScheduler(pipeline, registry)
    await scheduler._run_source_safe(config)
    await scheduler._run_source_safe(config)
    assert scheduler.get_consecutive_failures(config.name) == 2

    await scheduler._run_source_safe(config)
    assert scheduler.get_consecutive_failures(config.name) == 0
    assert registry.get_health(config.name).is_healthy is True


@pytest.mark.asyncio
async def test_scheduler_survives_individual_source_failure():
    config_a = _make_config("Source A")
    config_b = _make_config("Source B")
    registry = _make_registry(config_a, config_b)

    call_log: list[str] = []

    async def fake_run(config: SourceConfig) -> int:
        call_log.append(config.name)
        if config.name == "Source A":
            raise Exception("Source A is down")
        return 3

    pipeline = MagicMock()
    pipeline.run_source = AsyncMock(side_effect=fake_run)

    scheduler = ScrapeScheduler(pipeline, registry)

    with patch("src.scheduler.jobs.asyncio.sleep", new_callable=AsyncMock):
        await scheduler._run_all_sources()

    assert "Source A" in call_log
    assert "Source B" in call_log
    assert registry.get_health("Source B").success_count == 1


@pytest.mark.asyncio
async def test_scheduler_spreads_sources_across_interval():
    configs = [_make_config(f"Source {i}") for i in range(4)]
    registry = _make_registry(*configs)

    delays: list[float] = []

    async def capture_delay(self, config, delay):
        delays.append(delay)
        await self._run_source_safe(config)

    pipeline = MagicMock()
    pipeline.run_source = AsyncMock(return_value=0)
    scheduler = ScrapeScheduler(pipeline, registry)

    with patch.object(ScrapeScheduler, "_run_source_with_delay", capture_delay):
        await scheduler._run_all_sources()

    assert len(delays) == 4
    expected_step = SCRAPE_INTERVAL_SECONDS / 4
    assert delays[0] == 0.0
    assert abs(delays[1] - expected_step) < 0.001
    assert abs(delays[2] - 2 * expected_step) < 0.001


@pytest.mark.asyncio
async def test_scheduler_skips_when_no_active_sources():
    registry = _make_registry()
    pipeline = MagicMock()
    pipeline.run_source = AsyncMock(return_value=0)

    scheduler = ScrapeScheduler(pipeline, registry)
    await scheduler._run_all_sources()

    pipeline.run_source.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/admin/scrape-health
# ---------------------------------------------------------------------------


def _make_test_app(registry: SourceRegistry) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_router)
    app.state.registry = registry
    app.dependency_overrides[get_current_user] = lambda: _ADMIN_USER
    app.dependency_overrides[require_admin] = lambda: _ADMIN_USER
    return app


def test_admin_health_endpoint_returns_all_sources():
    config_a = _make_config("Source A")
    config_b = _make_config("Source B")
    registry = _make_registry(config_a, config_b)
    registry.record_success("Source A")
    registry.record_error("Source B", "timeout")

    client = TestClient(_make_test_app(registry))
    response = client.get("/api/admin/scrape-health")

    assert response.status_code == 200
    data = response.json()
    assert "sources" in data
    assert len(data["sources"]) == 2


def test_admin_health_endpoint_per_source_fields():
    config = _make_config("My Source")
    registry = _make_registry(config)
    registry.record_success("My Source")

    client = TestClient(_make_test_app(registry))
    response = client.get("/api/admin/scrape-health")

    source_data = response.json()["sources"]["my_source"]
    assert "is_healthy" in source_data
    assert "success_count" in source_data
    assert "error_count" in source_data
    assert "consecutive_failures" in source_data
    assert "success_rate" in source_data
    assert "last_scrape_time" in source_data
    assert "last_error" in source_data
    assert source_data["success_count"] == 1
    assert source_data["is_healthy"] is True


def test_admin_health_endpoint_shows_unhealthy_source():
    config = _make_config("Broken Source")
    registry = _make_registry(config)
    for _ in range(UNHEALTHY_THRESHOLD):
        registry.record_error("Broken Source", "connection refused")

    client = TestClient(_make_test_app(registry))
    response = client.get("/api/admin/scrape-health")

    source_data = response.json()["sources"]["broken_source"]
    assert source_data["is_healthy"] is False
    assert source_data["consecutive_failures"] == UNHEALTHY_THRESHOLD


def test_admin_health_requires_admin_role():
    registry = _make_registry()
    app = FastAPI()
    app.include_router(admin_router)
    app.state.registry = registry

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/scrape-health")
    assert response.status_code in (401, 403)
