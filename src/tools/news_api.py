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
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.news(
                query,
                region=region,
                max_results=min(max_results, 15),
            ))

        import src.db as db

        articles = []
        for r in results:
            url = r.get("url", "")
            date_str = r.get("date", "")
            
            weight = 0.5
            if url:
                weight = db.get_source_feedback_score(url)
                
            # Time Decay Logic
            if date_str:
                from datetime import datetime
                try:
                    article_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    now = datetime.now()
                    days_old = (now - article_date).days
                    
                    if days_old <= 1:
                        weight += 0.2  # Big bonus for today/yesterday
                    elif days_old <= 3:
                        weight += 0.1
                    elif days_old > 30:
                        weight -= 0.1  # Penalty for > 1 month old
                except Exception:
                    pass
                    
            if weight < 0.2:
                continue  # Skip consistently poorly-rated sources
                    
            articles.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "source": r.get("source", ""),
                "url": url,
                "date": r.get("date", ""),
                "rl_weight": weight
            })
            
        # Sort by RL weight descending
        articles.sort(key=lambda x: x["rl_weight"], reverse=True)

        return json.dumps({
            "query": query,
            "num_results": len(articles),
            "articles": articles,
        }, separators=(",", ":"), default=str)

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
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(
                query,
                max_results=min(max_results, 10),
            ))

        import src.db as db

        items = []
        for r in results:
            url = r.get("href", "")
            date_str = r.get("date", "")
            
            weight = 0.5
            if url:
                weight = db.get_source_feedback_score(url)
                
            if date_str:
                from datetime import datetime
                try:
                    article_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    now = datetime.now()
                    days_old = (now - article_date).days
                    
                    if days_old <= 1:
                        weight += 0.2
                    elif days_old <= 3:
                        weight += 0.1
                    elif days_old > 30:
                        weight -= 0.1
                except Exception:
                    pass
                    
            if weight < 0.2:
                continue
                
            items.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "href": url,
                "rl_weight": weight
            })
            
        items.sort(key=lambda x: x["rl_weight"], reverse=True)

        return json.dumps({
            "query": query,
            "num_results": len(items),
            "results": items,
        }, separators=(",", ":"), default=str)

    except Exception as e:
        return json.dumps({"error": f"Web search failed: {str(e)}"})


def get_geopolitical_news_tool():
    """Factory function returning the news tools."""
    return [search_geopolitical_news, search_web_general]
