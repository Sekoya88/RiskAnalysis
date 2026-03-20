"""
Backward-compatible shim — re-exports from new DDD locations.
"""

from src.container import search_geopolitical_news, search_web_general


def get_geopolitical_news_tool():
    return [search_geopolitical_news, search_web_general]


__all__ = ["search_geopolitical_news", "search_web_general", "get_geopolitical_news_tool"]
