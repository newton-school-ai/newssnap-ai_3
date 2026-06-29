from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CONFIGS_DIR = Path(__file__).parent / "source_configs"


class SourceHealth(BaseModel):
    last_scrape_time: Optional[datetime] = None
    success_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    is_healthy: bool = True

    @property
    def total_scrapes(self) -> int:
        return self.success_count + self.error_count

    @property
    def success_rate(self) -> float:
        if self.total_scrapes == 0:
            return 1.0
        return self.success_count / self.total_scrapes


class SourceConfig(BaseModel):
    name: str
    base_url: str
    scrape_type: str
    language: str = "en"
    category_slug: str = "national"
    priority: int = 1
    rate_limit_seconds: float = 2.0
    is_active: bool = True

    feed_url: Optional[str] = None
    article_list_url: Optional[str] = None
    article_link_selector: Optional[str] = None
    title_selector: Optional[str] = None
    body_selector: Optional[str] = None
    image_selector: Optional[str] = None
    date_selector: Optional[str] = None
    author_selector: Optional[str] = None

    category_mapping: dict[str, str] = Field(default_factory=dict)
    custom_headers: dict[str, str] = Field(default_factory=dict)


class SourceRegistry:
    def __init__(self, configs_dir: Path | str | None = None):
        self._configs_dir = Path(configs_dir) if configs_dir else CONFIGS_DIR
        self._sources: dict[str, SourceConfig] = {}
        self._health: dict[str, SourceHealth] = {}
        self._load_from_json()

    def _load_from_json(self) -> None:
        if not self._configs_dir.exists():
            logger.warning("Source configs directory not found: %s", self._configs_dir)
            return

        for json_file in sorted(self._configs_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                config = SourceConfig(**data)
                key = self._make_key(config.name)
                self._sources[key] = config
                self._health[key] = SourceHealth()
            except Exception:
                logger.exception("Failed to load source config: %s", json_file)

        logger.info("Loaded %d source configs from JSON", len(self._sources))

    def load_from_db_rows(self, rows: list[dict]) -> None:
        for row in rows:
            try:
                config = SourceConfig(
                    name=row["name"],
                    base_url=row["url"],
                    feed_url=row.get("feed_url"),
                    scrape_type=row["scrape_type"],
                    language=row.get("language", "en"),
                    category_slug=row.get("category_slug", "national"),
                    is_active=row.get("is_active", True),
                )
                key = self._make_key(config.name)
                if key not in self._sources:
                    self._sources[key] = config
                    self._health[key] = SourceHealth()
            except Exception:
                logger.exception("Failed to load source from DB row: %s", row.get("name"))

    def get_all_sources(self) -> list[SourceConfig]:
        return list(self._sources.values())

    def get_active_sources(self) -> list[SourceConfig]:
        return [s for s in self._sources.values() if s.is_active]

    def get_source(self, name: str) -> SourceConfig | None:
        return self._sources.get(self._make_key(name))

    def get_sources_by_type(self, scrape_type: str) -> list[SourceConfig]:
        return [s for s in self._sources.values() if s.scrape_type == scrape_type and s.is_active]

    def get_sources_by_language(self, language: str) -> list[SourceConfig]:
        return [s for s in self._sources.values() if s.language == language and s.is_active]

    def get_health(self, name: str) -> SourceHealth | None:
        return self._health.get(self._make_key(name))

    def get_all_health(self) -> dict[str, SourceHealth]:
        return dict(self._health)

    def record_success(self, name: str) -> None:
        key = self._make_key(name)
        health = self._health.get(key)
        if health:
            health.success_count += 1
            health.last_scrape_time = datetime.now(timezone.utc)
            health.is_healthy = True

    def record_error(self, name: str, error: str) -> None:
        key = self._make_key(name)
        health = self._health.get(key)
        if health:
            health.error_count += 1
            health.last_scrape_time = datetime.now(timezone.utc)
            health.last_error = error
            if health.error_count > 0 and health.success_rate < 0.5:
                health.is_healthy = False

    @staticmethod
    def _make_key(name: str) -> str:
        return name.lower().strip().replace(" ", "_")
