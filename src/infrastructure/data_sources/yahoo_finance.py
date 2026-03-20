"""Infrastructure — Yahoo Finance market data adapter."""

from __future__ import annotations

import yfinance as yf
from pydantic import BaseModel, Field
from typing import Optional


class MarketDataOutput(BaseModel):
    market_snapshot: dict = Field(default_factory=dict)
    financial_ratios: dict = Field(default_factory=dict)
    price_history: list[dict] = Field(default_factory=list)
    price_change_pct: float = 0.0
    error: Optional[str] = None


class YahooFinanceAdapter:
    """MarketDataPort implementation backed by Yahoo Finance (yfinance)."""

    def get_market_data(
        self,
        ticker: str,
        period: str = "1mo",
        include_financials: bool = True,
    ) -> str:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

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
                        ((hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0]) * 100, 2
                    )
                snapshot["price_change_pct"] = price_change_pct

            output = MarketDataOutput(
                market_snapshot=snapshot,
                financial_ratios=financials,
                price_history=price_history,
                price_change_pct=price_change_pct,
            )
            return output.model_dump_json()

        except Exception as e:
            output = MarketDataOutput(error=f"Failed to fetch data for {ticker.upper()}: {str(e)}")
            return output.model_dump_json()
