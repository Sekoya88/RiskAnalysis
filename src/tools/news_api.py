"""
Geopolitical News API Tool — Searches for real-time geopolitical and
macro-economic news using DuckDuckGo Search.

Provides the agent with contextual news articles related to:
  - Geopolitical tensions & sanctions
  - Trade wars & tariffs
  - Sovereign debt & macro-economic events
  - Supply chain disruptions
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# ── Schemas ──────────────────────────────────────────────────────────

class SearchGeopoliticalNewsInput(BaseModel):
    query: str = Field(
        ...,
        description="Search query (e.g. 'US China trade war impact tech sector 2025').",
    )
    region: str = Field(
        default="wt-wt",
        description="DuckDuckGo region code ('wt-wt' = worldwide, 'us-en', 'fr-fr').",
    )
    max_results: int = Field(
        default=8,
        description="Maximum number of results to return (1-15).",
    )


class NewsArticle(BaseModel):
    title: str = Field(default="")
    body: str = Field(default="")
    source: str = Field(default="")
    url: str = Field(default="")
    date: str = Field(default="")
    rl_weight: float = Field(default=0.5, description="RL feedback weight for this source.")


class SearchGeopoliticalNewsOutput(BaseModel):
    query: str = Field(default="")
    num_results: int = Field(default=0)
    articles: list[NewsArticle] = Field(default_factory=list)
    error: Optional[str] = Field(default=None)


class SearchWebGeneralInput(BaseModel):
    query: str = Field(..., description="Search query string.")
    max_results: int = Field(default=5, description="Maximum number of results (1-10).")


class WebSearchResult(BaseModel):
    title: str = Field(default="")
    body: str = Field(default="")
    href: str = Field(default="")
    rl_weight: float = Field(default=0.5, description="RL feedback weight for this source.")


class SearchWebGeneralOutput(BaseModel):
    query: str = Field(default="")
    num_results: int = Field(default=0)
    results: list[WebSearchResult] = Field(default_factory=list)
    error: Optional[str] = Field(default=None)


# ── RL weight computation ────────────────────────────────────────────

def _compute_rl_weight(url: str, date_str: str) -> float:
    """Compute RL weight for a source based on feedback history and time decay."""
    import src.db as db

    weight = 0.5
    if url:
        weight = db.get_source_feedback_score(url)

    if date_str:
        from datetime import datetime
        try:
            article_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            days_old = (datetime.now() - article_date).days
            if days_old <= 1:
                weight += 0.2
            elif days_old <= 3:
                weight += 0.1
            elif days_old > 30:
                weight -= 0.1
        except Exception:
            pass

    return weight


# ── Tools ────────────────────────────────────────────────────────────

@tool(args_schema=SearchGeopoliticalNewsInput)
def search_geopolitical_news(
    query: str,
    region: str = "wt-wt",
    max_results: int = 8,
) -> str:
    """Search for recent geopolitical and macro-economic news articles.

    Returns JSON with list of news articles including title, body snippet,
    source URL, publication date, and RL confidence weight.

    Args:
        query: Search query (e.g. 'US China trade war impact tech sector 2025').
        region: DuckDuckGo region code ('wt-wt' = worldwide, 'us-en', 'fr-fr').
        max_results: Maximum number of results to return (1-15).
    """
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.news(
                query,
                region=region,
                max_results=min(max_results, 15),
            ))

        articles: list[dict] = []
        for r in results:
            url = r.get("url", "")
            date_str = r.get("date", "")
            weight = _compute_rl_weight(url, date_str)

            if weight < 0.2:
                continue

            articles.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "source": r.get("source", ""),
                "url": url,
                "date": date_str,
                "rl_weight": weight,
            })

        articles.sort(key=lambda x: x["rl_weight"], reverse=True)

        output = SearchGeopoliticalNewsOutput(
            query=query,
            num_results=len(articles),
            articles=[NewsArticle(**a) for a in articles],
        )
        return output.model_dump_json()

    except Exception as e:
        output = SearchGeopoliticalNewsOutput(
            query=query, error=f"News search failed: {str(e)}"
        )
        return output.model_dump_json()


@tool(args_schema=SearchWebGeneralInput)
def search_web_general(
    query: str,
    max_results: int = 5,
) -> str:
    """Perform a general web search for background research and context.

    Returns JSON with search results including title, body snippet, URL,
    and RL confidence weight.

    Args:
        query: Search query string.
        max_results: Maximum number of results (1-10).
    """
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(
                query,
                max_results=min(max_results, 10),
            ))

        items: list[dict] = []
        for r in results:
            url = r.get("href", "")
            date_str = r.get("date", "")
            weight = _compute_rl_weight(url, date_str)

            if weight < 0.2:
                continue

            items.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "href": url,
                "rl_weight": weight,
            })

        items.sort(key=lambda x: x["rl_weight"], reverse=True)

        output = SearchWebGeneralOutput(
            query=query,
            num_results=len(items),
            results=[WebSearchResult(**i) for i in items],
        )
        return output.model_dump_json()

    except Exception as e:
        output = SearchWebGeneralOutput(
            query=query, error=f"Web search failed: {str(e)}"
        )
        return output.model_dump_json()


def get_geopolitical_news_tool():
    """Factory function returning the news tools."""
    return [search_geopolitical_news, search_web_general]
