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

import json
from typing import Optional

from langchain_core.tools import tool


@tool
def search_geopolitical_news(
    query: str,
    region: str = "wt-wt",
    max_results: int = 8,
) -> str:
    """Search for recent geopolitical and macro-economic news articles.

    Args:
        query: Search query (e.g. 'US China trade war impact tech sector 2025').
        region: DuckDuckGo region code ('wt-wt' = worldwide, 'us-en', 'fr-fr').
        max_results: Maximum number of results to return (1-15).

    Returns:
        JSON string with list of news articles including title, body snippet,
        source URL, and publication date.
    """
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.news(
                keywords=query,
                region=region,
                max_results=min(max_results, 15),
            ))

        articles = []
        for r in results:
            articles.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "source": r.get("source", ""),
                "url": r.get("url", ""),
                "date": r.get("date", ""),
            })

        return json.dumps({
            "query": query,
            "num_results": len(articles),
            "articles": articles,
        }, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": f"News search failed: {str(e)}"})


@tool
def search_web_general(
    query: str,
    max_results: int = 5,
) -> str:
    """Perform a general web search for background research and context.

    Args:
        query: Search query string.
        max_results: Maximum number of results.

    Returns:
        JSON string with search results.
    """
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(
                keywords=query,
                max_results=min(max_results, 10),
            ))

        items = []
        for r in results:
            items.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "href": r.get("href", ""),
            })

        return json.dumps({
            "query": query,
            "num_results": len(items),
            "results": items,
        }, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": f"Web search failed: {str(e)}"})


def get_geopolitical_news_tool():
    """Factory function returning the news tools."""
    return [search_geopolitical_news, search_web_general]
