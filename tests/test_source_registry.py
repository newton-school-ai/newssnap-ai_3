import json
import tempfile
from pathlib import Path

from src.scrapers.source_registry import SourceConfig, SourceRegistry


def _create_temp_configs(configs: list[dict]) -> Path:
    tmp_dir = Path(tempfile.mkdtemp())
    for i, cfg in enumerate(configs):
        (tmp_dir / f"source_{i}.json").write_text(json.dumps(cfg))
    return tmp_dir


SAMPLE_CONFIG = {
    "name": "Test Source",
    "base_url": "https://example.com",
    "scrape_type": "rss",
    "language": "en",
    "category_slug": "national",
    "feed_url": "https://example.com/rss",
    "priority": 1,
}

SAMPLE_CONFIG_2 = {
    "name": "Hindi Source",
    "base_url": "https://hindi.example.com",
    "scrape_type": "playwright",
    "language": "hi",
    "category_slug": "national",
    "priority": 2,
}

SAMPLE_INACTIVE = {
    "name": "Inactive Source",
    "base_url": "https://inactive.example.com",
    "scrape_type": "static",
    "language": "en",
    "category_slug": "sports",
    "is_active": False,
    "priority": 3,
}


def test_load_from_json():
    tmp_dir = _create_temp_configs([SAMPLE_CONFIG, SAMPLE_CONFIG_2])
    registry = SourceRegistry(configs_dir=tmp_dir)
    assert len(registry.get_all_sources()) == 2


def test_get_source_by_name():
    tmp_dir = _create_temp_configs([SAMPLE_CONFIG])
    registry = SourceRegistry(configs_dir=tmp_dir)
    source = registry.get_source("Test Source")
    assert source is not None
    assert source.base_url == "https://example.com"
    assert source.scrape_type == "rss"


def test_get_source_not_found():
    tmp_dir = _create_temp_configs([SAMPLE_CONFIG])
    registry = SourceRegistry(configs_dir=tmp_dir)
    assert registry.get_source("Nonexistent") is None


def test_get_active_sources():
    tmp_dir = _create_temp_configs([SAMPLE_CONFIG, SAMPLE_INACTIVE])
    registry = SourceRegistry(configs_dir=tmp_dir)
    active = registry.get_active_sources()
    assert len(active) == 1
    assert active[0].name == "Test Source"


def test_get_sources_by_type():
    tmp_dir = _create_temp_configs([SAMPLE_CONFIG, SAMPLE_CONFIG_2])
    registry = SourceRegistry(configs_dir=tmp_dir)
    rss_sources = registry.get_sources_by_type("rss")
    assert len(rss_sources) == 1
    assert rss_sources[0].name == "Test Source"


def test_get_sources_by_language():
    tmp_dir = _create_temp_configs([SAMPLE_CONFIG, SAMPLE_CONFIG_2])
    registry = SourceRegistry(configs_dir=tmp_dir)
    hindi_sources = registry.get_sources_by_language("hi")
    assert len(hindi_sources) == 1
    assert hindi_sources[0].name == "Hindi Source"


def test_load_from_db_rows():
    tmp_dir = _create_temp_configs([])
    registry = SourceRegistry(configs_dir=tmp_dir)
    registry.load_from_db_rows([
        {"name": "DB Source", "url": "https://db.example.com", "scrape_type": "rss", "language": "en"},
    ])
    assert len(registry.get_all_sources()) == 1
    assert registry.get_source("DB Source") is not None


def test_db_rows_do_not_overwrite_json():
    tmp_dir = _create_temp_configs([SAMPLE_CONFIG])
    registry = SourceRegistry(configs_dir=tmp_dir)
    registry.load_from_db_rows([
        {"name": "Test Source", "url": "https://other.com", "scrape_type": "static"},
    ])
    source = registry.get_source("Test Source")
    assert source.base_url == "https://example.com"


def test_health_tracking_success():
    tmp_dir = _create_temp_configs([SAMPLE_CONFIG])
    registry = SourceRegistry(configs_dir=tmp_dir)
    registry.record_success("Test Source")
    registry.record_success("Test Source")
    health = registry.get_health("Test Source")
    assert health.success_count == 2
    assert health.error_count == 0
    assert health.is_healthy is True
    assert health.last_scrape_time is not None


def test_health_tracking_errors():
    tmp_dir = _create_temp_configs([SAMPLE_CONFIG])
    registry = SourceRegistry(configs_dir=tmp_dir)
    registry.record_error("Test Source", "Connection timeout")
    health = registry.get_health("Test Source")
    assert health.error_count == 1
    assert health.last_error == "Connection timeout"


def test_health_unhealthy_after_many_errors():
    tmp_dir = _create_temp_configs([SAMPLE_CONFIG])
    registry = SourceRegistry(configs_dir=tmp_dir)
    registry.record_success("Test Source")
    for _ in range(5):
        registry.record_error("Test Source", "fail")
    health = registry.get_health("Test Source")
    assert health.is_healthy is False
    assert health.success_rate < 0.5


def test_health_for_unknown_source():
    tmp_dir = _create_temp_configs([])
    registry = SourceRegistry(configs_dir=tmp_dir)
    assert registry.get_health("Unknown") is None


def test_source_config_defaults():
    config = SourceConfig(name="Test", base_url="https://example.com", scrape_type="rss")
    assert config.language == "en"
    assert config.category_slug == "national"
    assert config.is_active is True
    assert config.rate_limit_seconds == 2.0
    assert config.priority == 1


def test_loads_real_configs():
    registry = SourceRegistry()
    sources = registry.get_all_sources()
    assert len(sources) >= 10
    names = [s.name for s in sources]
    assert "NDTV" in names
    assert "The Hindu" in names
    scrape_types = {s.scrape_type for s in sources}
    assert "rss" in scrape_types
    assert "playwright" in scrape_types
    assert "static" in scrape_types
