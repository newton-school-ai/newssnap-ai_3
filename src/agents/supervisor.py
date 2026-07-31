"""NewsSnap AI - Content pipeline supervisor.

Orchestrates the agents that turn scraped articles into snap-ready content.
Issue 11 wires in the summarizer stage; the dedup (Issue 9) and story clustering
(Issue 10) stages are accepted as injected callables so they can be plugged in
without changing this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.agents.summarizer_agent import SummarizerAgent, SummaryResult
from src.utils.text_utils import count_words

logger = logging.getLogger(__name__)

MIN_BODY_WORDS = 80


@dataclass
class PipelineStats:
    received: int = 0
    skipped: int = 0
    summarized: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "received": self.received,
            "skipped": self.skipped,
            "summarized": self.summarized,
            "failed": self.failed,
        }


@dataclass
class PipelineResult:
    articles: list[dict] = field(default_factory=list)
    stats: PipelineStats = field(default_factory=PipelineStats)


class ContentPipeline:
    """Run scraped articles through the content agents in order."""

    def __init__(
        self,
        summarizer: Optional[SummarizerAgent] = None,
        dedup_agent: Optional[Callable[[list[dict]], list[dict]]] = None,
        clusterer: Optional[Callable[[list[dict]], list[dict]]] = None,
        min_body_words: int = MIN_BODY_WORDS,
        skip_existing: bool = True,
    ) -> None:
        self.summarizer = summarizer or SummarizerAgent()
        self.dedup_agent = dedup_agent
        self.clusterer = clusterer
        self.min_body_words = min_body_words
        self.skip_existing = skip_existing

    def run(self, articles: list[dict]) -> PipelineResult:
        """Summarize a batch of articles, returning them with summary metadata attached."""
        stats = PipelineStats(received=len(articles))
        if not articles:
            return PipelineResult(articles=[], stats=stats)

        working = [dict(article) for article in articles]

        if self.dedup_agent is not None:
            working = self.dedup_agent(working)
            logger.info("dedup stage kept %s of %s articles", len(working), stats.received)

        if self.clusterer is not None:
            working = self.clusterer(working)

        pending = [article for article in working if self._needs_summary(article)]
        stats.skipped = len(working) - len(pending)

        if pending:
            results = self.summarizer.batch_summarize_detailed(pending)
            for article, result in zip(pending, results):
                self._attach(article, result)
                if result.is_valid:
                    stats.summarized += 1
                else:
                    stats.failed += 1
                    logger.warning(
                        "summary rejected for %s: %s",
                        article.get("url") or article.get("title"),
                        "; ".join(result.issues),
                    )

        return PipelineResult(articles=working, stats=stats)

    # -- internals ----------------------------------------------------------

    def _needs_summary(self, article: dict) -> bool:
        if self.skip_existing and (article.get("summary") or "").strip():
            return False

        body = article.get("body") or article.get("content") or ""
        if count_words(body) < self.min_body_words:
            logger.debug("skipping short article: %s", article.get("url") or article.get("title"))
            return False

        return True

    @staticmethod
    def _attach(article: dict, result: SummaryResult) -> None:
        article["summary"] = result.summary
        article["summary_metadata"] = summary_metadata(result)


def summary_metadata(result: SummaryResult) -> dict[str, Any]:
    """Metadata stored beside the summary. Source attribution lives here, not in the text."""
    return {
        "word_count": result.word_count,
        "language": result.language,
        "category": result.category,
        "is_valid": result.is_valid,
        "attempts": result.attempts,
        "facts_present": result.facts,
        "issues": result.issues,
        "model": result.model,
        "source_name": result.source_name,
        "source_url": result.source_url,
        "attribution": result.attribution,
    }
