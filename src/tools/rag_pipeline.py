"""
Vector DB RAG Pipeline Tool — Hybrid search (Vector + BM25) over corporate
disclosures, annual reports, and financial documents.

This module:
  1. Initializes a persistent Chroma vector store.
  2. Seeds it with sample corporate disclosure documents on first run.
  3. Exposes a LangChain tool for **hybrid** retrieval (semantic + keyword).

Hybrid search combines:
  - ChromaDB vector similarity (semantic understanding)
  - BM25 keyword matching (exact term retrieval)
  - Reciprocal Rank Fusion (RRF) to merge both result sets
"""

from __future__ import annotations

import glob
import os
import re
from collections import defaultdict
from typing import Optional

from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field

# ── Constants ─────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "chroma_db",
)
DOCS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "docs",
)
COLLECTION_NAME = "corporate_disclosures"

# Hybrid search weights: 60% semantic, 40% keyword (BM25)
VECTOR_WEIGHT = 0.6
BM25_WEIGHT = 0.4
# RRF constant (standard value from the original RRF paper)
RRF_K = 60


# ── Schemas ──────────────────────────────────────────────────────────

class SearchCorporateDisclosuresInput(BaseModel):
    query: str = Field(
        ...,
        description="Search query describing what information you need.",
    )
    num_results: int = Field(
        default=5,
        description="Number of relevant documents to retrieve (1-10).",
    )
    company_filter: Optional[str] = Field(
        default=None,
        description=(
            "Optional company name. If provided, prioritizes documents for that "
            "company while still including broad macro/geopolitical outlooks."
        ),
    )


class RetrievedDocument(BaseModel):
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
    documents: list[RetrievedDocument] = Field(default_factory=list)
    error: Optional[str] = Field(default=None)


# ── Internals ────────────────────────────────────────────────────────

def _get_embeddings():
    """Get HuggingFace embedding model (runs locally, no API key needed)."""
    return HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def _load_local_docs() -> list[Document]:
    """Scans DOCS_DIR for PDFs, loads them, and splits them into chunks."""
    all_docs = []
    pdf_files = glob.glob(os.path.join(DOCS_DIR, "*.pdf"))

    if not pdf_files:
        print(f"⚠️  No PDF files found in {DOCS_DIR}")
        return []

    print(f"📚 Loading {len(pdf_files)} documents from {DOCS_DIR}...")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )

    for pdf_path in pdf_files:
        try:
            loader = PyPDFLoader(pdf_path)
            docs = loader.load_and_split(text_splitter=text_splitter)

            filename = os.path.basename(pdf_path)
            company = "Global"
            company_match = re.search(r"([A-Z][a-z]+)", filename)
            if company_match:
                potential = company_match.group(1)
                if any(kw in filename.lower() for kw in ["risks", "outlook", "wef", "fitch", "global"]):
                    company = "Global"
                else:
                    company = potential

            for doc in docs:
                doc.metadata["source"] = filename
                doc.metadata["company"] = company
                doc.metadata["type"] = "pdf_report"

            all_docs.extend(docs)
            print(f"   ✅ Loaded {filename} ({len(docs)} chunks)")
        except Exception as e:
            print(f"   ❌ Failed to load {pdf_path}: {e}")

    print(f"📊 Total: {len(all_docs)} chunks from {len(pdf_files)} documents")
    return all_docs


def _initialize_vector_store() -> Chroma:
    """Initialize ChromaDB vector store, seeding with local docs if empty."""
    embeddings = _get_embeddings()
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
    )

    existing = vectorstore.get()
    if len(existing.get("ids", [])) == 0:
        docs = _load_local_docs()
        if docs:
            print(f"🚀 Ingesting {len(docs)} chunks into ChromaDB...")
            vectorstore.add_documents(docs)
            print("   ✅ Ingestion complete.")

    return vectorstore


# ── Module-level singletons ───────────────────────────────────────────
_vectorstore: Chroma | None = None
_bm25_docs: list[Document] | None = None


def _get_store() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = _initialize_vector_store()
    return _vectorstore


def _get_bm25_docs() -> list[Document]:
    """Get or lazily load all documents for BM25 keyword search."""
    global _bm25_docs
    if _bm25_docs is None:
        store = _get_store()
        all_data = store.get(include=["documents", "metadatas"])
        docs = []
        for content, metadata in zip(
            all_data.get("documents", []),
            all_data.get("metadatas", []),
        ):
            if content:
                docs.append(Document(page_content=content, metadata=metadata or {}))
        _bm25_docs = docs
        print(f"📝 BM25 index built with {len(docs)} chunks")
    return _bm25_docs


def _reciprocal_rank_fusion(
    vector_results: list[Document],
    bm25_results: list[Document],
    vector_weight: float = VECTOR_WEIGHT,
    bm25_weight: float = BM25_WEIGHT,
    k: int = RRF_K,
) -> list[tuple[Document, float]]:
    """Merge two ranked result lists using weighted Reciprocal Rank Fusion."""
    scores: dict[str, float] = defaultdict(float)
    doc_map: dict[str, Document] = {}

    for rank, doc in enumerate(vector_results):
        key = doc.page_content[:300]
        scores[key] += vector_weight * (1.0 / (k + rank + 1))
        doc_map[key] = doc

    for rank, doc in enumerate(bm25_results):
        key = doc.page_content[:300]
        scores[key] += bm25_weight * (1.0 / (k + rank + 1))
        if key not in doc_map:
            doc_map[key] = doc

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(doc_map[key], score) for key, score in ranked]


def _hybrid_search(
    query: str,
    num_results: int = 5,
    filter_dict: dict | None = None,
) -> list[dict]:
    """Perform hybrid search combining vector similarity + BM25 keyword matching."""
    store = _get_store()
    bm25_docs = _get_bm25_docs()

    fetch_k = min(num_results * 2, 20)
    vector_results = store.similarity_search(
        query=query, k=fetch_k, filter=filter_dict,
    )

    if bm25_docs:
        if filter_dict:
            allowed_companies = set()
            for cond in filter_dict.get("$or", []):
                if "company" in cond:
                    allowed_companies.add(cond["company"])
            if allowed_companies:
                filtered_docs = [
                    d for d in bm25_docs
                    if d.metadata.get("company", "") in allowed_companies
                ]
            else:
                filtered_docs = bm25_docs
        else:
            filtered_docs = bm25_docs

        if not filtered_docs:
            filtered_docs = bm25_docs

        bm25_retriever = BM25Retriever.from_documents(filtered_docs, k=fetch_k)
        bm25_results = bm25_retriever.invoke(query)
    else:
        bm25_results = []

    if bm25_results:
        fused = _reciprocal_rank_fusion(vector_results, bm25_results)
        retrieval_method = "hybrid (vector + BM25)"
    else:
        fused = [(doc, 1.0 - i * 0.05) for i, doc in enumerate(vector_results)]
        retrieval_method = "vector"

    documents = []
    for doc, score in fused[:num_results]:
        documents.append({
            "content": doc.page_content,
            "source": doc.metadata.get("source", "unknown"),
            "company": doc.metadata.get("company", "unknown"),
            "document_type": doc.metadata.get("type", "unknown"),
            "page": str(doc.metadata.get("page", "N/A")),
            "relevance_score": round(score, 4),
            "retrieval_method": retrieval_method,
        })

    return documents


# ── Tool ─────────────────────────────────────────────────────────────

@tool(args_schema=SearchCorporateDisclosuresInput)
def search_corporate_disclosures(
    query: str,
    num_results: int = 5,
    company_filter: str | None = None,
) -> str:
    """Search the integrated risk disclosure database using hybrid retrieval
    (semantic vector search + BM25 keyword matching).

    IMPORTANT: This database contains NOT ONLY corporate filings (10-Ks, etc.)
    but also BROAD MACRO-ECONOMIC and GEOPOLITICAL RISK REPORTS (e.g., WEF,
    Fitch, Apollo Outlooks).

    The hybrid search combines:
    - Semantic similarity (understands meaning, e.g. "currency risk" = "FX exposure")
    - Keyword matching (finds exact terms like "Altman Z-Score", "EBITDA", tickers)

    Use this tool to ground your analysis in factual data and reduce hallucination risk.

    Args:
        query: Search query describing what information you need.
        num_results: Number of relevant documents to retrieve (1-10).
        company_filter: Optional company name to prioritize in search results.
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

        documents = _hybrid_search(
            query=query,
            num_results=min(num_results, 10),
            filter_dict=filter_dict,
        )

        output = SearchCorporateDisclosuresOutput(
            query=query,
            num_results=len(documents),
            documents=[RetrievedDocument(**d) for d in documents],
        )
        return output.model_dump_json(indent=2)

    except Exception as e:
        output = SearchCorporateDisclosuresOutput(
            query=query, error=f"RAG search failed: {str(e)}"
        )
        return output.model_dump_json()


def get_rag_tool():
    """Factory function returning the RAG pipeline tool."""
    return search_corporate_disclosures
