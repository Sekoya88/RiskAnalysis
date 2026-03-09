"""
Backward-compatible shim — re-exports from new DDD locations.

The actual RAG logic is now in:
  - src/infrastructure/vector_store/chroma.py
  - src/infrastructure/retrieval/hybrid.py
  - src/infrastructure/embeddings/ollama.py (embeddinggemma)

LangChain @tool functions are in src/container.py.
"""

from src.container import search_corporate_disclosures, get_hybrid_retriever


def get_rag_tool():
    return search_corporate_disclosures


__all__ = ["search_corporate_disclosures", "get_rag_tool"]
