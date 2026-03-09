"""
Dependency Injection Container — Wires all layers together.

This is the composition root. It creates infrastructure adapters,
injects them into application agents, and registers LangChain tools.

Usage:
    from src.container import bootstrap
    bootstrap()  # Call once at startup
"""

from __future__ import annotations

import os
import queue
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.infrastructure.config.providers import get_embedding_config, get_vector_store_config, get_retrieval_config
from src.infrastructure.embeddings.factory import create_embeddings
from src.infrastructure.vector_store.chroma import ChromaVectorStoreAdapter
from src.infrastructure.retrieval.hybrid import HybridRetriever
from src.infrastructure.data_sources.yahoo_finance import YahooFinanceAdapter
from src.infrastructure.data_sources.duckduckgo import DuckDuckGoAdapter
from src.infrastructure.persistence.sqlite import SQLiteReportRepository, SQLiteFeedbackRepository
from src.infrastructure.persistence.memory import FileMemoryAdapter

# ── Resolve project paths ──────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
_DB_PATH = os.path.join(_DATA_DIR, "risk_history.db")
_CHROMA_DIR = os.path.join(_DATA_DIR, "chroma_db")
_DOCS_DIR = os.path.join(_DATA_DIR, "docs")
_MEMORY_PATH = os.path.join(_DATA_DIR, "AGENTS.md")

# ── Singleton adapters (lazily initialized) ─────────────────────────
_report_repo: SQLiteReportRepository | None = None
_feedback_repo: SQLiteFeedbackRepository | None = None
_memory_adapter: FileMemoryAdapter | None = None
_market_adapter: YahooFinanceAdapter | None = None
_news_adapter: DuckDuckGoAdapter | None = None
_hybrid_retriever: HybridRetriever | None = None
_bootstrapped = False


def get_report_repo() -> SQLiteReportRepository:
    global _report_repo
    if _report_repo is None:
        _report_repo = SQLiteReportRepository(_DB_PATH)
    return _report_repo


def get_feedback_repo() -> SQLiteFeedbackRepository:
    global _feedback_repo
    if _feedback_repo is None:
        _feedback_repo = SQLiteFeedbackRepository(_DB_PATH)
    return _feedback_repo


def get_memory_adapter() -> FileMemoryAdapter:
    global _memory_adapter
    if _memory_adapter is None:
        _memory_adapter = FileMemoryAdapter(_MEMORY_PATH)
    return _memory_adapter


def get_market_adapter() -> YahooFinanceAdapter:
    global _market_adapter
    if _market_adapter is None:
        _market_adapter = YahooFinanceAdapter()
    return _market_adapter


def get_news_adapter() -> DuckDuckGoAdapter:
    global _news_adapter
    if _news_adapter is None:
        _news_adapter = DuckDuckGoAdapter(feedback_repo=get_feedback_repo())
    return _news_adapter


def get_hybrid_retriever() -> HybridRetriever:
    global _hybrid_retriever
    if _hybrid_retriever is None:
        vs_config = get_vector_store_config()
        ret_config = get_retrieval_config()

        embedding = create_embeddings()
        vector_store = ChromaVectorStoreAdapter(
            embedding=embedding,
            persist_directory=vs_config.get("persist_directory", _CHROMA_DIR),
            collection_name=vs_config.get("collection_name", "corporate_disclosures"),
            docs_directory=_DOCS_DIR,
        )
        _hybrid_retriever = HybridRetriever(
            vector_store=vector_store,
            vector_weight=ret_config.get("vector_weight", 0.6),
            bm25_weight=ret_config.get("bm25_weight", 0.4),
            rrf_k=ret_config.get("rrf_k", 60),
        )
    return _hybrid_retriever


# ── LangChain Tool Schemas ──────────────────────────────────────────

class GetMarketDataInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol (e.g. 'AAPL', 'MSFT').")
    period: str = Field(default="1mo", description="Historical price period.")
    include_financials: bool = Field(default=True, description="Include balance-sheet ratios.")


class SearchGeopoliticalNewsInput(BaseModel):
    query: str = Field(..., description="Search query for geopolitical news.")
    region: str = Field(default="wt-wt", description="DuckDuckGo region code.")
    max_results: int = Field(default=8, description="Max results (1-15).")


class SearchWebGeneralInput(BaseModel):
    query: str = Field(..., description="Search query string.")
    max_results: int = Field(default=5, description="Max results (1-10).")


class SearchCorporateDisclosuresInput(BaseModel):
    query: str = Field(..., description="Search query for corporate disclosures.")
    num_results: int = Field(default=5, description="Number of results (1-10).")
    company_filter: str | None = Field(default=None, description="Optional company name filter.")


class RetrievedDocumentOutput(BaseModel):
    content: str = Field(default="")
    source: str = Field(default="unknown")
    company: str = Field(default="unknown")
    document_type: str = Field(default="unknown")
    page: str = Field(default="N/A")
    relevance_score: float = Field(default=0.0)
    retrieval_method: str = Field(default="hybrid")


class SearchCorporateDisclosuresOutput(BaseModel):
    query: str = Field(default="")
    num_results: int = Field(default=0)
    retrieval_method: str = Field(default="hybrid (vector + BM25)")
    documents: list[RetrievedDocumentOutput] = Field(default_factory=list)
    error: str | None = Field(default=None)


# ── LangChain @tool wrappers (delegate to adapters) ────────────────

@tool(args_schema=GetMarketDataInput)
def get_market_data(ticker: str, period: str = "1mo", include_financials: bool = True) -> str:
    """Fetch real-time market data, price history, and key financial ratios for a given stock ticker."""
    return get_market_adapter().get_market_data(ticker, period, include_financials)


@tool(args_schema=SearchGeopoliticalNewsInput)
def search_geopolitical_news(query: str, region: str = "wt-wt", max_results: int = 8) -> str:
    """Search for recent geopolitical and macro-economic news articles."""
    return get_news_adapter().search_news(query, region, max_results)


@tool(args_schema=SearchWebGeneralInput)
def search_web_general(query: str, max_results: int = 5) -> str:
    """Perform a general web search for background research and context."""
    return get_news_adapter().search_web(query, max_results)


@tool(args_schema=SearchCorporateDisclosuresInput)
def search_corporate_disclosures(query: str, num_results: int = 5, company_filter: str | None = None) -> str:
    """Search the integrated risk disclosure database using hybrid retrieval
    (semantic vector search + BM25 keyword matching).

    This database contains corporate filings AND broad macro-economic/geopolitical
    risk reports (WEF, Fitch, Apollo Outlooks).
    """
    try:
        filter_dict = None
        if company_filter:
            filter_dict = {
                "$or": [
                    {"company": company_filter},
                    {"company": "Global"},
                    {"company": "General Risk"},
                    {"company": "Industry Report"},
                    {"company": "General"},
                ]
            }

        documents = get_hybrid_retriever().search(
            query=query,
            num_results=min(num_results, 10),
            filter_dict=filter_dict,
        )

        output = SearchCorporateDisclosuresOutput(
            query=query,
            num_results=len(documents),
            documents=[RetrievedDocumentOutput(**d) for d in documents],
        )
        return output.model_dump_json(indent=2)

    except Exception as e:
        return SearchCorporateDisclosuresOutput(
            query=query, error=f"RAG search failed: {str(e)}"
        ).model_dump_json()


# ── Tool sets per agent ─────────────────────────────────────────────
GEOPOLITICAL_TOOLS = [search_geopolitical_news, search_web_general, search_corporate_disclosures]
CREDIT_TOOLS = [get_market_data, search_corporate_disclosures, search_web_general]
SYNTHESIZER_TOOLS = [search_corporate_disclosures, search_web_general]

# Tool registry for dispatch
TOOL_REGISTRY = {
    "search_geopolitical_news": search_geopolitical_news,
    "search_web_general": search_web_general,
    "search_corporate_disclosures": search_corporate_disclosures,
    "get_market_data": get_market_data,
}


def bootstrap(log_queue: queue.Queue | None = None) -> None:
    """Wire all adapters and configure agent nodes. Call once at startup."""
    global _bootstrapped
    if _bootstrapped:
        return

    from src.application.agents import base, geopolitical, credit, synthesizer

    # Register tools in the base module for dispatch
    base.register_tools(TOOL_REGISTRY)

    # Configure each agent node with its tools and adapters
    geopolitical.configure(tools=GEOPOLITICAL_TOOLS, log_queue=log_queue)
    credit.configure(tools=CREDIT_TOOLS, log_queue=log_queue)
    synthesizer.configure(
        tools=SYNTHESIZER_TOOLS,
        memory_adapter=get_memory_adapter(),
        log_queue=log_queue,
    )

    _bootstrapped = True


def reset() -> None:
    """Reset bootstrap state (for testing)."""
    global _bootstrapped
    _bootstrapped = False
