from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DEFAULT_QUALITY_THRESHOLD = 0.4
DEFAULT_MIN_BODY_WORDS = 100
TARGET_BODY_WORDS = 400

LENGTH_WEIGHT = 0.4
COHERENCE_WEIGHT = 0.35
COMPLETENESS_WEIGHT = 0.25

_CLICKBAIT_TITLE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"you won.?t believe",
        r"\bshocking\b",
        r"what happened next",
        r"gone wrong",
        r"this one (weird |simple )?trick",
        r"number \d+ will",
        r"doctors hate",
        r"\bmust see\b",
        r"\bunbelievable\b",
        r"jaw.?dropping",
        r"^\d+ (things|reasons|ways|facts|photos|pics)",
        r"will (blow|melt) your mind",
        r"\bwatch\b.*\bviral\b|\bviral\b.*\bwatch\b",
    ]
]

_SPONSORED_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bsponsored\b",
        r"\badvertorial\b",
        r"\bpromoted content\b",
        r"\bpaid partnership\b",
        r"\bin partnership with\b",
        r"\badvertisement\b",
        r"\bbrand ?voice\b",
        r"this is a sponsored post",
    ]
]

_COMPLETENESS_MARKERS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\.\.\.\s*$",
        r"continue reading",
        r"\bread more\b",
        r"read full story",
        r"\[?read the full article\]?",
    ]
]

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "is", "are", "was", "were", "be", "as", "by", "it", "its", "this",
    "that", "from", "into", "amid", "over", "after", "before", "how", "why",
}


@dataclass
class QualityResult:
    article_id: str
    score: float
    is_rejected: bool
    reason: Optional[str] = None


class QualityFilter:
    def __init__(
        self,
        threshold: float = DEFAULT_QUALITY_THRESHOLD,
        min_body_words: int = DEFAULT_MIN_BODY_WORDS,
    ):
        self.threshold = threshold
        self.min_body_words = min_body_words

    def count_words(self, text: str) -> int:
        return len((text or "").split())

    def is_clickbait(self, title: str) -> bool:
        if not title:
            return False
        if any(p.search(title) for p in _CLICKBAIT_TITLE_PATTERNS):
            return True
        if title.count("!") >= 2 or title.count("?") >= 2:
            return True
        letters = [c for c in title if c.isalpha()]
        if letters and len(letters) > 8:
            upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if upper_ratio > 0.6:
                return True
        return False

    def is_sponsored(self, title: str, content: str) -> bool:
        text = f"{title or ''} {content or ''}"
        return any(p.search(text) for p in _SPONSORED_PATTERNS)

    def length_score(self, content: str) -> float:
        words = self.count_words(content)
        if words <= 0:
            return 0.0
        return max(0.0, min(words / TARGET_BODY_WORDS, 1.0))

    def _keywords(self, text: str) -> set[str]:
        words = re.findall(r"[a-zA-Z']+", text or "")
        return {w.lower() for w in words if len(w) > 2 and w.lower() not in _STOPWORDS}

    def coherence_score(self, title: str, content: str) -> float:
        title_words = self._keywords(title)
        if not title_words:
            return 0.5
        body_words = self._keywords(content)
        overlap = title_words & body_words
        return len(overlap) / len(title_words)

    def completeness_score(self, content: str) -> float:
        if not content or not content.strip():
            return 0.0
        if any(p.search(content) for p in _COMPLETENESS_MARKERS):
            return 0.3
        return 1.0

    def score_article(self, title: str, content: str) -> float:
        length = self.length_score(content)
        coherence = self.coherence_score(title, content)
        completeness = self.completeness_score(content)
        combined = (
            length * LENGTH_WEIGHT
            + coherence * COHERENCE_WEIGHT
            + completeness * COMPLETENESS_WEIGHT
        )
        return round(max(0.0, min(combined, 1.0)), 4)

    def evaluate(self, article_id: str, title: str, content: str) -> QualityResult:
        word_count = self.count_words(content)
        score = self.score_article(title, content)

        if word_count < self.min_body_words:
            return QualityResult(
                article_id, score, True,
                f"body too short ({word_count} words, min {self.min_body_words})",
            )
        if self.is_clickbait(title):
            return QualityResult(article_id, score, True, "clickbait title detected")
        if self.is_sponsored(title, content):
            return QualityResult(article_id, score, True, "sponsored content detected")
        if score < self.threshold:
            return QualityResult(
                article_id, score, True,
                f"quality score {score} below threshold {self.threshold}",
            )
        return QualityResult(article_id, score, False, None)

    def run(self, db: Session) -> list[QualityResult]:
        from sqlalchemy import select

        from src.models.article import Article

        articles = db.scalars(select(Article).where(Article.quality_score.is_(None))).all()
        if not articles:
            return []

        results: list[QualityResult] = []
        for article in articles:
            result = self.evaluate(str(article.id), article.title or "", article.content or "")
            article.quality_score = result.score
            article.is_rejected = result.is_rejected
            article.rejection_reason = result.reason
            results.append(result)

        db.commit()
        logger.info(
            "Quality filter run complete: %d processed, %d rejected",
            len(results),
            sum(1 for r in results if r.is_rejected),
        )
        return results
