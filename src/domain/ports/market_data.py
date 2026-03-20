"""Port — Market data provider abstraction (Protocol)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MarketDataPort(Protocol):
    """Abstract interface for market data providers.

    Implementations: YahooFinanceAdapter.
    """

    def get_market_data(self, ticker: str, period: str = "1mo", include_financials: bool = True) -> str:
        """Fetch market data as JSON string."""
        ...
