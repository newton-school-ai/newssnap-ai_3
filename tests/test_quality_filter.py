from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.agents.quality_filter import (
    DEFAULT_MIN_BODY_WORDS,
    DEFAULT_QUALITY_THRESHOLD,
    QualityFilter,
    QualityResult,
)
from src.api.admin import router as admin_router
from src.api.middleware import CurrentUser, get_current_user, require_admin
from src.db.session import get_db
from src.models.article import Article
from src.models.base import Base
from src.models.source import Source  # noqa: F401 (table registration)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _words(n: int, prefix: str = "word") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def _filter(**kwargs) -> QualityFilter:
    return QualityFilter(**kwargs)


GOOD_TITLE = "Government announces new infrastructure policy for rural connectivity"
GOOD_CONTENT = (
    "The government announced a major new infrastructure policy today covering rural "
    "connectivity, digital expansion, and highway construction across twelve states. "
) * 20  # well over 100 words, title keywords repeated in body


# ---------------------------------------------------------------------------
# Defaults / configuration
# ---------------------------------------------------------------------------


def test_default_threshold():
    assert _filter().threshold == DEFAULT_QUALITY_THRESHOLD


def test_default_min_body_words():
    assert _filter().min_body_words == DEFAULT_MIN_BODY_WORDS


def test_configurable_threshold():
    assert _filter(threshold=0.6).threshold == 0.6


def test_configurable_min_body_words():
    assert _filter(min_body_words=50).min_body_words == 50


# ---------------------------------------------------------------------------
# count_words
# ---------------------------------------------------------------------------


def test_count_words_basic():
    assert _filter().count_words("one two three") == 3


def test_count_words_empty_or_none():
    assert _filter().count_words("") == 0
    assert _filter().count_words(None) == 0


# ---------------------------------------------------------------------------
# is_clickbait
# ---------------------------------------------------------------------------


def test_is_clickbait_known_phrase():
    assert _filter().is_clickbait("You won't believe what happened next") is True


def test_is_clickbait_numbered_listicle():
    assert _filter().is_clickbait("10 things doctors don't want you to know") is True


def test_is_clickbait_excessive_punctuation():
    assert _filter().is_clickbait("Massive win for India!! What a moment!!") is True


def test_is_clickbait_shouting_caps():
    assert _filter().is_clickbait("THIS IS THE BIGGEST SCANDAL EVER SEEN") is True


def test_is_clickbait_false_for_normal_headline():
    assert _filter().is_clickbait(GOOD_TITLE) is False


def test_is_clickbait_empty_title():
    assert _filter().is_clickbait("") is False


# ---------------------------------------------------------------------------
# is_sponsored
# ---------------------------------------------------------------------------


def test_is_sponsored_in_title():
    assert _filter().is_sponsored("Sponsored: Best deals this festive season", "content") is True


def test_is_sponsored_in_body():
    assert _filter().is_sponsored("Title", "This is a sponsored post in partnership with BrandX.") is True


def test_is_sponsored_false_for_normal_article():
    assert _filter().is_sponsored(GOOD_TITLE, GOOD_CONTENT) is False


def test_is_sponsored_advertorial():
    assert _filter().is_sponsored("An advertorial feature", "regular text") is True


# ---------------------------------------------------------------------------
# length_score / coherence_score / completeness_score
# ---------------------------------------------------------------------------


def test_length_score_zero_for_empty_content():
    assert _filter().length_score("") == 0.0


def test_length_score_scales_with_word_count():
    short_score = _filter().length_score(_words(50))
    long_score = _filter().length_score(_words(400))
    assert 0.0 < short_score < long_score <= 1.0


def test_length_score_caps_at_one():
    assert _filter().length_score(_words(1000)) == 1.0


def test_coherence_score_high_when_title_words_in_body():
    agent = _filter()
    score = agent.coherence_score("budget announcement finance minister", "the budget announcement by the finance minister was well received")
    assert score > 0.8


def test_coherence_score_low_when_title_body_mismatch():
    agent = _filter()
    score = agent.coherence_score("cricket world cup final victory", "the weather today is sunny with clear skies across the region")
    assert score < 0.3


def test_coherence_score_neutral_for_empty_title():
    assert _filter().coherence_score("", "some content here") == 0.5


def test_completeness_score_full_for_normal_content():
    assert _filter().completeness_score(GOOD_CONTENT) == 1.0


def test_completeness_score_zero_for_empty():
    assert _filter().completeness_score("") == 0.0


def test_completeness_score_penalizes_truncation_marker():
    score = _filter().completeness_score("This article was cut short and continues elsewhere... continue reading")
    assert score < 1.0


# ---------------------------------------------------------------------------
# score_article
# ---------------------------------------------------------------------------


def test_score_article_high_for_good_article():
    score = _filter().score_article(GOOD_TITLE, GOOD_CONTENT)
    assert score >= 0.7


def test_score_article_low_for_thin_incoherent_article():
    score = _filter().score_article("Big news today", "unrelated short filler text")
    assert score < 0.4


def test_score_article_bounded_between_zero_and_one():
    score = _filter().score_article(GOOD_TITLE, GOOD_CONTENT)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# evaluate(): acceptance criteria
# ---------------------------------------------------------------------------


def test_evaluate_rejects_body_under_100_words():
    agent = _filter()
    result = agent.evaluate("a1", GOOD_TITLE, _words(50))
    assert result.is_rejected is True
    assert "short" in result.reason


def test_evaluate_accepts_body_over_100_words_with_good_quality():
    agent = _filter()
    result = agent.evaluate("a1", GOOD_TITLE, GOOD_CONTENT)
    assert result.is_rejected is False
    assert result.reason is None


def test_evaluate_rejects_clickbait():
    agent = _filter()
    result = agent.evaluate("a1", "You won't believe what happened next!!", GOOD_CONTENT)
    assert result.is_rejected is True
    assert "clickbait" in result.reason


def test_evaluate_rejects_sponsored_content():
    agent = _filter()
    result = agent.evaluate("a1", "Sponsored: Amazing new product launch", GOOD_CONTENT)
    assert result.is_rejected is True
    assert "sponsored" in result.reason


def test_evaluate_rejects_below_threshold_score():
    agent = _filter(threshold=0.99)  # deliberately stricter than GOOD_CONTENT's ~0.95 score
    result = agent.evaluate("a1", GOOD_TITLE, GOOD_CONTENT)
    assert result.is_rejected is True
    assert "quality score" in result.reason


def test_evaluate_threshold_configurable():
    lenient = _filter(threshold=0.01)
    strict = _filter(threshold=0.99)
    title, content = "Some ordinary headline", _words(150)

    lenient_result = lenient.evaluate("a1", title, content)
    strict_result = strict.evaluate("a1", title, content)

    assert lenient_result.score == strict_result.score
    assert strict_result.is_rejected is True


def test_evaluate_returns_quality_result_type():
    result = _filter().evaluate("a1", GOOD_TITLE, GOOD_CONTENT)
    assert isinstance(result, QualityResult)
    assert result.article_id == "a1"


# ---------------------------------------------------------------------------
# run() integration (DB mocked)
# ---------------------------------------------------------------------------


def _make_mock_article(article_id: str, title: str, content: str) -> MagicMock:
    article = MagicMock()
    article.id = article_id
    article.title = title
    article.content = content
    article.quality_score = None
    article.is_rejected = False
    article.rejection_reason = None
    return article


def _make_mock_db(articles: list) -> MagicMock:
    db = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = articles
    db.scalars.return_value = scalars_result
    return db


def test_run_returns_empty_when_no_unscored_articles():
    db = _make_mock_db([])
    results = _filter().run(db)
    assert results == []
    db.commit.assert_not_called()


def test_run_persists_score_and_rejection_on_good_article():
    article = _make_mock_article("a1", GOOD_TITLE, GOOD_CONTENT)
    db = _make_mock_db([article])

    results = _filter().run(db)

    assert len(results) == 1
    assert results[0].is_rejected is False
    assert article.quality_score == results[0].score
    assert article.is_rejected is False
    assert article.rejection_reason is None
    db.commit.assert_called_once()


def test_run_persists_rejection_reason_on_bad_article():
    article = _make_mock_article("a1", "SHOCKING news you won't believe!!", _words(30))
    db = _make_mock_db([article])

    results = _filter().run(db)

    assert results[0].is_rejected is True
    assert article.is_rejected is True
    assert article.rejection_reason is not None
    db.commit.assert_called_once()


def test_run_processes_multiple_articles():
    good = _make_mock_article("good", GOOD_TITLE, GOOD_CONTENT)
    bad = _make_mock_article("bad", "SHOCKING!!", _words(10))
    db = _make_mock_db([good, bad])

    results = _filter().run(db)

    assert len(results) == 2
    result_map = {r.article_id: r for r in results}
    assert result_map["good"].is_rejected is False
    assert result_map["bad"].is_rejected is True


def test_run_always_sets_quality_score_even_when_rejected():
    article = _make_mock_article("a1", "Sponsored content here", GOOD_CONTENT)
    db = _make_mock_db([article])

    _filter().run(db)

    assert article.quality_score is not None


# ---------------------------------------------------------------------------
# GET /api/admin/rejected-articles (real SQLite-backed FastAPI app)
# ---------------------------------------------------------------------------

_ADMIN_USER = CurrentUser(user_id="admin-1", role="admin")


def _make_admin_test_app() -> tuple[FastAPI, "sessionmaker"]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_current_user] = lambda: _ADMIN_USER
    app.dependency_overrides[require_admin] = lambda: _ADMIN_USER
    app.dependency_overrides[get_db] = override_get_db
    return app, session_local


def _seed_article(session_local, is_rejected: bool, reason: str | None, title: str = "Title") -> None:
    db = session_local()
    now = datetime.now(timezone.utc)
    db.add(
        Article(
            id=uuid.uuid4(),
            url=f"https://example.com/{uuid.uuid4()}",
            title=title,
            content="Some content",
            category_slug="national",
            quality_score=0.1 if is_rejected else 0.9,
            is_rejected=is_rejected,
            rejection_reason=reason,
            publish_time=now,
        )
    )
    db.commit()
    db.close()


def test_rejected_articles_endpoint_returns_only_rejected():
    app, session_local = _make_admin_test_app()
    _seed_article(session_local, is_rejected=True, reason="clickbait title detected", title="Bad Article")
    _seed_article(session_local, is_rejected=False, reason=None, title="Good Article")

    client = TestClient(app)
    response = client.get("/api/admin/rejected-articles")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["articles"]) == 1
    assert data["articles"][0]["title"] == "Bad Article"
    assert data["articles"][0]["rejection_reason"] == "clickbait title detected"


def test_rejected_articles_endpoint_empty_when_none_rejected():
    app, session_local = _make_admin_test_app()
    _seed_article(session_local, is_rejected=False, reason=None)

    client = TestClient(app)
    response = client.get("/api/admin/rejected-articles")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["articles"] == []


def test_rejected_articles_endpoint_respects_limit():
    app, session_local = _make_admin_test_app()
    for i in range(5):
        _seed_article(session_local, is_rejected=True, reason="too short", title=f"Bad {i}")

    client = TestClient(app)
    response = client.get("/api/admin/rejected-articles?limit=2")

    data = response.json()
    assert data["total"] == 5
    assert len(data["articles"]) == 2


def test_rejected_articles_endpoint_requires_admin():
    # No auth overrides at all: the real get_current_user/require_admin chain
    # runs and must reject the request before any DB dependency is touched.
    app = FastAPI()
    app.include_router(admin_router)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/admin/rejected-articles")

    assert response.status_code in (401, 403)
