from __future__ import annotations

import concurrent.futures
import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, TypedDict

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_MIN_WORDS = 60
DEFAULT_MAX_WORDS = 80
DEFAULT_MAX_RETRIES = 2
DEFAULT_MAX_WORKERS = 10

CATEGORY_STYLE_HINTS: dict[str, str] = {
    "finance": "Lead with the number or market move that matters most. Precise, no hype.",
    "business": "Lead with the number or market move that matters most. Precise, no hype.",
    "sports": "Lead with the result. Capture the moment without exaggerating.",
    "politics": "Stay strictly neutral. State positions and facts, not opinions.",
    "technology": "Explain what is new and why a reader should care, plainly.",
    "science": "Explain what was found or done and why it matters, plainly.",
    "entertainment": "Engaging tone, but state facts only, no speculation framed as fact.",
    "health": "Be precise about medical claims. Avoid alarming language.",
    "crime": "Factual and restrained. No sensationalism.",
}
DEFAULT_STYLE_HINT = "Write in a clear, neutral, informative tone."

_CLICKBAIT_PATTERNS = [
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
    ]
]


@dataclass
class SummaryResult:
    story_id: str
    summary: Optional[str]
    attempts: int
    success: bool
    error: Optional[str] = None


class _SummarizerState(TypedDict):
    title: str
    content: str
    category: str
    attempts: int
    summary: Optional[str]
    valid: bool
    error: Optional[str]


class SummarizerAgent:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        min_words: int = DEFAULT_MIN_WORDS,
        max_words: int = DEFAULT_MAX_WORDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_workers: int = DEFAULT_MAX_WORKERS,
        api_key: Optional[str] = None,
        temperature: float = 0.3,
    ):
        self.model_name = model_name
        self.min_words = min_words
        self.max_words = max_words
        self.max_retries = max_retries
        self.max_workers = max_workers
        self.temperature = temperature
        self._api_key = api_key or os.getenv("GROQ_API_KEY")
        self._client = None
        self._graph = None

    @property
    def client(self):
        if self._client is None:
            from langchain_groq import ChatGroq

            self._client = ChatGroq(
                model_name=self.model_name,
                groq_api_key=self._api_key,
                temperature=self.temperature,
            )
        return self._client

    @property
    def graph(self):
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    def style_hint(self, category: str) -> str:
        return CATEGORY_STYLE_HINTS.get((category or "").lower(), DEFAULT_STYLE_HINT)

    def build_prompt(self, title: str, content: str, category: str) -> str:
        hint = self.style_hint(category)
        return (
            "You are a news editor writing a crisp summary for a mobile news app.\n"
            f"Category: {category}. Style: {hint}\n"
            f"Write exactly one paragraph of {self.min_words}-{self.max_words} words summarizing "
            "the article below. Preserve the key facts: who, what, when, where, and why. "
            "Be strictly factual, no clickbait, no speculation, no exaggeration, no questions "
            "used as hooks. Output only the paragraph, with no headline or title.\n\n"
            f"Title: {title}\n\nArticle:\n{content}\n\nSummary:"
        )

    def count_words(self, text: str) -> int:
        return len(text.split())

    def is_clickbait(self, text: str) -> bool:
        return any(p.search(text) for p in _CLICKBAIT_PATTERNS)

    def validate_summary(self, text: str) -> tuple[bool, Optional[str]]:
        if not text or not text.strip():
            return False, "empty summary"
        word_count = self.count_words(text)
        if word_count < self.min_words:
            return False, f"too short ({word_count} words, min {self.min_words})"
        if word_count > self.max_words:
            return False, f"too long ({word_count} words, max {self.max_words})"
        if self.is_clickbait(text):
            return False, "clickbait language detected"
        return True, None

    def generate_summary(self, title: str, content: str, category: str) -> str:
        prompt = self.build_prompt(title, content, category)
        response = self.client.invoke(prompt)
        text = getattr(response, "content", response)
        return str(text).strip()

    def _build_graph(self):
        from langgraph.graph import END, StateGraph

        def generate_node(state: _SummarizerState) -> _SummarizerState:
            summary = self.generate_summary(state["title"], state["content"], state["category"])
            return {**state, "summary": summary, "attempts": state["attempts"] + 1}

        def validate_node(state: _SummarizerState) -> _SummarizerState:
            valid, error = self.validate_summary(state["summary"] or "")
            return {**state, "valid": valid, "error": error}

        def should_retry(state: _SummarizerState) -> str:
            if state["valid"]:
                return "end"
            if state["attempts"] > self.max_retries:
                return "end"
            return "retry"

        graph = StateGraph(_SummarizerState)
        graph.add_node("generate", generate_node)
        graph.add_node("validate", validate_node)
        graph.set_entry_point("generate")
        graph.add_edge("generate", "validate")
        graph.add_conditional_edges("validate", should_retry, {"retry": "generate", "end": END})
        return graph.compile()

    def summarize(self, story_id: str, title: str, content: str, category: str) -> SummaryResult:
        initial: _SummarizerState = {
            "title": title,
            "content": content,
            "category": category,
            "attempts": 0,
            "summary": None,
            "valid": False,
            "error": None,
        }
        final_state = self.graph.invoke(initial)
        return SummaryResult(
            story_id=story_id,
            summary=final_state["summary"] if final_state["valid"] else None,
            attempts=final_state["attempts"],
            success=final_state["valid"],
            error=final_state.get("error"),
        )

    def summarize_batch(self, items: list[dict]) -> list[SummaryResult]:
        if not items:
            return []

        results: list[Optional[SummaryResult]] = [None] * len(items)
        workers = max(1, min(self.max_workers, len(items)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_idx = {
                executor.submit(
                    self.summarize, item["story_id"], item["title"], item["content"], item["category"]
                ): idx
                for idx, item in enumerate(items)
            }
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                results[idx] = future.result()

        return results  # type: ignore[return-value]

    def run(self, db: Session) -> list[SummaryResult]:
        from sqlalchemy import select

        from src.models.story import Story

        stories = db.scalars(select(Story).where(Story.summary.is_(None))).all()
        if not stories:
            return []

        items = []
        for story in stories:
            articles = getattr(story, "articles", None) or []
            combined = " ".join(
                f"{a.title}. {a.content or a.summary or ''}".strip() for a in articles
            ).strip()
            if not combined:
                combined = story.title
            items.append(
                {
                    "story_id": str(story.id),
                    "title": story.title,
                    "content": combined,
                    "category": story.category_slug,
                }
            )

        results = self.summarize_batch(items)

        id_to_story = {str(s.id): s for s in stories}
        for result in results:
            if result.success and result.summary:
                story = id_to_story.get(result.story_id)
                if story is not None:
                    story.summary = result.summary

        db.commit()
        logger.info(
            "Summarizer run complete: %d processed, %d succeeded",
            len(results),
            sum(1 for r in results if r.success),
        )
        return results
