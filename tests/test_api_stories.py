import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.api.main import app
from src.db.session import get_db
from src.models.article import Article
from src.models.base import Base
from src.models.source import Source  # noqa: F401 (For table registration)
from src.models.story import Story

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = testing_session_local()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_get_story():
    db = testing_session_local()

    story_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Create story and articles
    story = Story(
        id=story_id,
        title="Main Story",
        category_slug="tech",
        language="en",
        importance_score=0.8,
        article_count=2,
        first_seen_at=now,
        last_updated_at=now,
    )

    a1 = Article(
        id=uuid.uuid4(),
        title="Related 1",
        url="http://r1",
        category_slug="tech",
        quality_score=0.5,
        publish_time=now,
        story_id=story_id,
    )
    a2 = Article(
        id=uuid.uuid4(),
        title="Primary",
        url="http://p1",
        category_slug="tech",
        quality_score=0.9,
        publish_time=now,
        story_id=story_id,
    )

    db.add_all([story, a1, a2])
    db.commit()
    db.close()

    response = client.get(f"/api/stories/{story_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["title"] == "Main Story"
    assert data["primary_article"]["title"] == "Primary"
    assert len(data["related_articles"]) == 1
    assert data["related_articles"][0]["title"] == "Related 1"


def test_get_story_not_found():
    random_id = uuid.uuid4()
    response = client.get(f"/api/stories/{random_id}")
    assert response.status_code == 404
