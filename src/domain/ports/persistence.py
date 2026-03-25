"""Port — Persistence abstractions (Protocol)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ReportRepositoryPort(Protocol):
    """Abstract interface for report persistence."""

    def save_report(self, report_id: str, entity: str, scores: dict, report_text: str, sources: dict) -> None:
        ...

    def get_history_for_entity(self, entity: str) -> list[dict[str, Any]]:
        ...


@runtime_checkable
class FeedbackRepositoryPort(Protocol):
    """Abstract interface for RL feedback persistence."""

    def save_feedback(self, report_id: str, news_url: str, is_helpful: bool, comments: str = "") -> None:
        ...

    def get_source_feedback_score(self, url: str) -> float:
        ...

    def list_feedback_votes(self) -> list[tuple[str, bool]]:
        """All (news_url, is_helpful) rows for PPO / offline RL training."""
        ...


@runtime_checkable
class MemoryPort(Protocol):
    """Abstract interface for agent persistent memory."""

    def load(self) -> str:
        ...

    def update(self, entity: str, scores: dict, date: str | None = None) -> None:
        ...
