"""Port — News/web search abstraction (Protocol)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class NewsPort(Protocol):
    """Abstract interface for news and web search providers.

    Implementations: DuckDuckGoAdapter.
    """

    def search_news(self, query: str, region: str = "wt-wt", max_results: int = 8) -> str:
        """Search geopolitical/macro news. Returns JSON string."""
        ...

    def search_web(self, query: str, max_results: int = 5) -> str:
        """General web search. Returns JSON string."""
        ...
