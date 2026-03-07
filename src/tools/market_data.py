"""
Market Data Tool — Fetches real-time and historical financial data
using the Yahoo Finance API via yfinance.

Provides the agent with:
  - Current price, P/E, market cap, 52-week range
  - Key balance-sheet ratios (Debt/Equity, Current Ratio)
  - Recent price history (last 30 days)
"""

from __future__ import annotations

from typing import Optional

import yfinance as yf
from langchain_core.tools import tool
from pydantic import BaseModel, Field


# ── Schemas ──────────────────────────────────────────────────────────

class GetMarketDataInput(BaseModel):
    ticker: str = Field(
        ...,
        description="Stock ticker symbol (e.g. 'AAPL', 'MSFT', 'LVMH.PA').",
    )
    period: str = Field(
        default="1mo",
        description="Historical price period — '1d','5d','1mo','3mo','6mo','1y','2y'.",
    )
    include_financials: bool = Field(
        default=True,
        description="If True, include balance-sheet ratios and earnings.",
    )


class GetMarketDataOutput(BaseModel):
    market_snapshot: dict = Field(default_factory=dict, description="Core market data snapshot.")
    financial_ratios: dict = Field(default_factory=dict, description="Financial ratios (if requested).")
    price_history: list[dict] = Field(default_factory=list, description="Recent price records.")
    price_change_pct: float = Field(default=0.0, description="Price change percentage over the period.")
    error: Optional[str] = Field(default=None, description="Error message if the tool fails.")


# ── Tool ─────────────────────────────────────────────────────────────

@tool(args_schema=GetMarketDataInput)
def get_market_data(
    ticker: str,
    period: str = "1mo",
    include_financials: bool = True,
) -> str:
    """Fetch real-time market data, price history, and key financial ratios
    for a given stock ticker.

    Args:
        ticker: Stock ticker symbol (e.g. 'AAPL', 'MSFT', 'LVMH.PA').
        period: Historical price period — '1d','5d','1mo','3mo','6mo','1y','2y'.
        include_financials: If True, include balance-sheet ratios and earnings.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # ── Core market snapshot ───────────────────────────────────────
        snapshot: dict = {
            "ticker": ticker.upper(),
            "name": info.get("longName", info.get("shortName", ticker)),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "currency": info.get("currency", "USD"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "previous_close": info.get("previousClose"),
            "market_cap": info.get("marketCap"),
            "pe_ratio_trailing": info.get("trailingPE"),
            "pe_ratio_forward": info.get("forwardPE"),
            "dividend_yield": info.get("dividendYield"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "50_day_average": info.get("fiftyDayAverage"),
            "200_day_average": info.get("twoHundredDayAverage"),
            "beta": info.get("beta"),
        }

        # ── Financial ratios ──────────────────────────────────────────
        financials: dict = {}
        if include_financials:
            financials = {
                "revenue": info.get("totalRevenue"),
                "gross_margins": info.get("grossMargins"),
                "operating_margins": info.get("operatingMargins"),
                "profit_margins": info.get("profitMargins"),
                "debt_to_equity": info.get("debtToEquity"),
                "current_ratio": info.get("currentRatio"),
                "return_on_equity": info.get("returnOnEquity"),
                "return_on_assets": info.get("returnOnAssets"),
                "free_cash_flow": info.get("freeCashflow"),
                "earnings_growth": info.get("earningsGrowth"),
                "revenue_growth": info.get("revenueGrowth"),
            }
            snapshot["financials"] = financials

            snapshot["credit_signals"] = {
                "total_debt": info.get("totalDebt"),
                "total_cash": info.get("totalCash"),
                "ebitda": info.get("ebitda"),
                "quick_ratio": info.get("quickRatio"),
                "recommendation": info.get("recommendationKey"),
                "target_mean_price": info.get("targetMeanPrice"),
                "number_of_analyst_opinions": info.get("numberOfAnalystOpinions"),
            }

        # ── Price history (compact) ───────────────────────────────────
        price_history: list[dict] = []
        price_change_pct = 0.0
        hist = stock.history(period=period)
        if not hist.empty:
            for date, row in hist.tail(5).iterrows():
                price_history.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "close": round(row["Close"], 2),
                    "volume": int(row["Volume"]),
                })
            snapshot["recent_prices"] = price_history
            if hist["Close"].iloc[0] != 0:
                price_change_pct = round(
                    ((hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0]) * 100,
                    2,
                )
            snapshot["price_change_pct"] = price_change_pct

        output = GetMarketDataOutput(
            market_snapshot=snapshot,
            financial_ratios=financials,
            price_history=price_history,
            price_change_pct=price_change_pct,
        )
        return output.model_dump_json()

    except Exception as e:
        output = GetMarketDataOutput(
            error=f"Failed to fetch data for {ticker.upper()}: {str(e)}"
        )
        return output.model_dump_json()


def get_market_data_tool():
    """Factory function returning the market data tool."""
    return get_market_data
