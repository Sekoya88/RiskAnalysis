"""
Vector DB RAG Pipeline Tool — Semantic search over corporate disclosures,
annual reports, and financial documents using ChromaDB + embeddings.

This module:
  1. Initializes a persistent Chroma vector store.
  2. Seeds it with sample corporate disclosure documents on first run.
  3. Exposes a LangChain tool for semantic retrieval.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_community.embeddings import HuggingFaceEmbeddings


# ── Constants ─────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "chroma_db",
)
COLLECTION_NAME = "corporate_disclosures"

# ── Sample corporate disclosures for seeding ──────────────────────────
SAMPLE_DOCUMENTS = [
    Document(
        page_content="""Apple Inc. Annual Report 2024 - Risk Factors:
        The company faces significant supply chain concentration risk in Asia-Pacific,
        particularly in China and Taiwan. Approximately 85% of iPhone assembly occurs
        in China through Foxconn and Pegatron. Geopolitical tensions between the US and
        China, including potential export restrictions on advanced semiconductors, could
        materially impact production capacity. The company has begun diversifying
        manufacturing to India and Vietnam, but full transition is estimated at 3-5 years.
        Currency fluctuations in CNY, INR, and VND present hedging challenges.
        Total long-term debt stands at $98.3B with a debt-to-equity ratio of 1.73.""",
        metadata={"source": "AAPL_10K_2024", "company": "Apple Inc.", "type": "annual_report"},
    ),
    Document(
        page_content="""Tesla Inc. Q4 2024 Earnings - Key Highlights:
        Revenue grew 12% YoY to $27.1B driven by Model Y demand in Europe and China.
        However, margins compressed to 17.6% from 23.8% due to aggressive pricing strategy.
        Shanghai Gigafactory production reached 950K units/year but faces regulatory
        scrutiny over data localization requirements. European operations impacted by
        new EU battery regulation (2025 enforcement). Cybertruck ramp slower than expected.
        Free cash flow of $2.1B. Lithium supply agreements with Chilean and Australian
        miners secured through 2028, reducing raw material geopolitical exposure.""",
        metadata={"source": "TSLA_Q4_2024", "company": "Tesla Inc.", "type": "earnings_report"},
    ),
    Document(
        page_content="""LVMH Moët Hennessy Louis Vuitton SE - Credit Assessment 2024:
        S&P rating: A+/Stable. Strong free cash flow generation of €8.2B supports
        investment-grade profile. Geographic revenue diversification: Asia-Pacific 31%,
        Europe 25%, US 25%, Rest of World 19%. Key risk factors include luxury demand
        sensitivity to Chinese economic slowdown, with Chinese consumers representing
        approximately 35% of global luxury spend. Ongoing tariff uncertainties between
        EU and US could impact cognac and wine segments (Hennessy). Net debt/EBITDA
        ratio of 0.8x provides substantial headroom. Acquisition of Tiffany & Co
        integration proceeding ahead of synergy targets.""",
        metadata={"source": "LVMH_CREDIT_2024", "company": "LVMH", "type": "credit_assessment"},
    ),
    Document(
        page_content="""JPMorgan Chase & Co - Sovereign Risk Analysis Q1 2025:
        Emerging market sovereign debt concerns elevated. Argentina's restructuring
        negotiations stalled; CDS spreads widened to 1,800bps. Turkey's unorthodox
        monetary policy continues to pressure TRY; inflation at 58%. Egypt secured
        $8B IMF Extended Fund Facility but implementation risks remain high.
        China's property sector defaults (Evergrande, Country Garden) creating
        systemic credit transmission risks. US Treasury yields inverted yield curve
        persists, suggesting recession probability at 45% (NY Fed model).
        Geopolitical flash points: Taiwan Strait, South China Sea, Middle East
        energy corridor disruptions affecting Brent crude volatility.""",
        metadata={"source": "JPM_SOVEREIGN_Q1_2025", "company": "JPMorgan", "type": "sovereign_analysis"},
    ),
    Document(
        page_content="""TotalEnergies SE - ESG and Geopolitical Risk Profile 2024:
        Operations in 130+ countries with significant exposure to politically
        unstable regions. Nigerian operations face ongoing Niger Delta security
        challenges and regulatory uncertainty post-Petroleum Industry Act.
        Russian asset write-downs of €4.1B completed; Arctic LNG 2 project
        participation under EU sanctions review. New LNG investments in
        Mozambique (Area 1) delayed due to Cabo Delgado insurgency.
        Middle East portfolio: 10% of production from UAE and Qatar, exposed
        to Strait of Hormuz transit risk. Energy transition investments
        of €5B/year targeting 35GW renewable capacity by 2025.
        Credit rating: Aa3/AA- with negative watch due to transition risks.""",
        metadata={"source": "TTE_ESG_2024", "company": "TotalEnergies", "type": "esg_report"},
    ),
    Document(
        page_content="""Global Semiconductor Supply Chain Risk Assessment 2025:
        TSMC controls 56% of global foundry market, with 92% of sub-7nm production.
        US CHIPS Act driving $52.7B in domestic semiconductor investment, but
        full capacity not expected until 2027. Samsung Foundry expanding in Texas;
        Intel Foundry Services restructuring. China's SMIC advancing to 7nm without
        EUV, raising IP concerns. Export controls on ASML EUV equipment to China
        remain contentious EU-US-Netherlands policy issue. Automotive chip shortage
        easing but AI accelerator demand (NVIDIA H100/H200) creating new bottlenecks.
        Geopolitical scenario: Taiwan contingency would eliminate 37% of global
        chip production capacity, estimated $500B+ annual economic impact.""",
        metadata={"source": "SEMI_SUPPLY_2025", "company": "Industry Report", "type": "supply_chain_analysis"},
    ),
]


def _get_embeddings():
    """Get HuggingFace embedding model (runs locally, no API key needed)."""
    return HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def _initialize_vector_store() -> Chroma:
    """Initialize ChromaDB vector store, seeding with sample docs if empty."""
    embeddings = _get_embeddings()
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
    )

    # Seed if the collection is empty
    existing = vectorstore.get()
    if len(existing.get("ids", [])) == 0:
        vectorstore.add_documents(SAMPLE_DOCUMENTS)

    return vectorstore


# ── Module-level singleton ────────────────────────────────────────────
_vectorstore: Chroma | None = None


def _get_store() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = _initialize_vector_store()
    return _vectorstore


@tool
def search_corporate_disclosures(
    query: str,
    num_results: int = 4,
    company_filter: str | None = None,
) -> str:
    """Search the corporate disclosures vector database for semantically
    relevant documents (annual reports, credit assessments, ESG reports).

    Use this tool to ground your analysis in factual corporate data and
    reduce hallucination risk.

    Args:
        query: Semantic search query describing what information you need.
        num_results: Number of relevant documents to retrieve (1-10).
        company_filter: Optional company name to filter results.

    Returns:
        JSON string with relevant document excerpts and metadata.
    """
    try:
        store = _get_store()

        filter_dict = None
        if company_filter:
            filter_dict = {"company": company_filter}

        results = store.similarity_search_with_relevance_scores(
            query=query,
            k=min(num_results, 10),
            filter=filter_dict,
        )

        documents = []
        for doc, score in results:
            documents.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "company": doc.metadata.get("company", "unknown"),
                "document_type": doc.metadata.get("type", "unknown"),
                "relevance_score": round(score, 4),
            })

        return json.dumps({
            "query": query,
            "num_results": len(documents),
            "documents": documents,
        }, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": f"RAG search failed: {str(e)}"})


def get_rag_tool():
    """Factory function returning the RAG pipeline tool."""
    return search_corporate_disclosures
