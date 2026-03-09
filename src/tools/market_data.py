"""
Backward-compatible shim — re-exports from new DDD locations.
"""

from src.container import get_market_data


def get_market_data_tool():
    return get_market_data


__all__ = ["get_market_data", "get_market_data_tool"]
