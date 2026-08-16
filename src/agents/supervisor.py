from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.agents.dedup_agent import DedupAgent, DeduplicationResult
    from src.agents.story_clusterer import ClusteringResult, StoryClusterer
    from src.agents.summarizer_agent import SummarizerAgent, SummaryResult

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    dedup: "DeduplicationResult"
    clustering: "ClusteringResult"
    summaries: list["SummaryResult"]


class ContentPipelineSupervisor:
    """Runs the article content pipeline in order: dedup -> cluster -> summarize."""

    def __init__(
        self,
        dedup_agent: Optional["DedupAgent"] = None,
        story_clusterer: Optional["StoryClusterer"] = None,
        summarizer_agent: Optional["SummarizerAgent"] = None,
    ):
        from src.agents.dedup_agent import DedupAgent
        from src.agents.story_clusterer import StoryClusterer
        from src.agents.summarizer_agent import SummarizerAgent

        self.dedup_agent = dedup_agent or DedupAgent()
        self.story_clusterer = story_clusterer or StoryClusterer()
        self.summarizer_agent = summarizer_agent or SummarizerAgent()

    def run(self, db: Session, registry=None) -> PipelineResult:
        dedup_result = self.dedup_agent.run(db, registry=registry)
        clustering_result = self.story_clusterer.run(db)
        summary_results = self.summarizer_agent.run(db)

        logger.info(
            "Pipeline complete: dedup %d/%d unique, %d stories created, %d/%d summaries succeeded",
            dedup_result.unique_count,
            dedup_result.processed,
            clustering_result.stories_created,
            sum(1 for r in summary_results if r.success),
            len(summary_results),
        )
        return PipelineResult(
            dedup=dedup_result,
            clustering=clustering_result,
            summaries=summary_results,
        )
