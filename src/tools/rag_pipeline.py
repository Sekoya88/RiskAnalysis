"""
Vector DB RAG Pipeline Tool — Semantic search over corporate disclosures,
annual reports, and financial documents using ChromaDB + embeddings.

This module:
  1. Initializes a persistent Chroma vector store.
  2. Seeds it with sample corporate disclosure documents on first run.
  3. Exposes a LangChain tool for semantic retrieval.
"""

from __future__ import annotations

import glob
import json
import os
import re

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

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
        chunk_overlap=100,
    )

    for pdf_path in pdf_files:
        try:
            loader = PyPDFLoader(pdf_path)
            # Load and split in one go
            docs = loader.load_and_split(text_splitter=text_splitter)
            
            # Enrich metadata
            filename = os.path.basename(pdf_path)
            # Infer company or categorize as Global
            company = "Global"
            company_match = re.search(r"([A-Z][a-z]+)", filename)
            if company_match:
                potential = company_match.group(1)
                # If filename looks like a summary or outlook, it's Global
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

    return all_docs


def _initialize_vector_store() -> Chroma:
    """Initialize ChromaDB vector store, seeding with local docs if empty."""
    embeddings = _get_embeddings()
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
    )

    # Seed if the collection is empty
    existing = vectorstore.get()
    if len(existing.get("ids", [])) == 0:
        docs = _load_local_docs()
        if docs:
            print(f"🚀 Ingesting {len(docs)} chunks into ChromaDB...")
            vectorstore.add_documents(docs)
            print("   ✅ Ingestion complete.")

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
    num_results: int = 5,
    company_filter: str | None = None,
) -> str:
    """Search the integrated risk disclosure database for semantically
    relevant documents.

    IMPORTANT: This database contains NOT ONLY corporate filings (10-Ks, etc.)
    but also BROAD MACRO-ECONOMIC and GEOPOLITICAL RISK REPORTS (e.g., WEF, 
    Fitch, Apollo Outlooks).

    Use this tool to ground your analysis in factual data and reduce 
    hallucination risk.

    Args:
        query: Semantic search query describing what information you need.
        num_results: Number of relevant documents to retrieve (1-10).
        company_filter: Optional company name. If provided, the search will
            prioritize documents for that company while STILL including 
            broad macro/geopolitical outlooks.

    Returns:
        JSON string with relevant document excerpts and metadata.
    """
    try:
        store = _get_store()

        filter_dict = None
        if company_filter:
            # Match specific company OR general/global/industry reports
            filter_dict = {
                "$or": [
                    {"company": company_filter},
                    {"company": "Global"},
                    {"company": "General Risk"},
                    {"company": "Industry Report"},
                    {"company": "General"},
                ]
            }

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
