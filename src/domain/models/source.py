"""
Domain Models — Source entities and value objects.

Represents all data sources used by agents (news, market, RAG documents).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Source(BaseModel):
    """Base source entity with RL weight."""

    url: str = Field(default="")
    title: str = Field(default="")
    rl_weight: float = Field(default=0.5, description="RL feedback weight")


class NewsArticle(Source):
    """A news article from search."""

    body: str = Field(default="")
    source: str = Field(default="")
    date: str = Field(default="")


class WebResult(Source):
    """A general web search result."""

    body: str = Field(default="")
    href: str = Field(default="")


class MarketSnapshot(BaseModel):
    """Market data snapshot for an entity."""

    ticker: str = ""
    name: str = ""
    sector: str = "N/A"
    industry: str = "N/A"
    currency: str = "USD"
    current_price: Optional[float] = None
    previous_close: Optional[float] = None
    market_cap: Optional[int] = None
    pe_ratio_trailing: Optional[float] = None
    pe_ratio_forward: Optional[float] = None
    dividend_yield: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    beta: Optional[float] = None
    financials: dict = Field(default_factory=dict)
    credit_signals: dict = Field(default_factory=dict)
    recent_prices: list[dict] = Field(default_factory=list)
    price_change_pct: float = 0.0


class RetrievedDocument(BaseModel):
    """A document retrieved from the RAG pipeline."""

    content: str = Field(default="")
    source: str = Field(default="unknown")
    company: str = Field(default="unknown")
    document_type: str = Field(default="unknown")
    page: str = Field(default="N/A")
    relevance_score: float = Field(default=0.0)
    retrieval_method: str = Field(default="hybrid")
