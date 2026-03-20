"""Infrastructure — Hybrid Retrieval (Vector + BM25 with RRF fusion)."""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from src.domain.ports.vector_store import VectorStorePort


# Default weights and constants
VECTOR_WEIGHT = 0.6
BM25_WEIGHT = 0.4
RRF_K = 60


class HybridRetriever:
    """Combines vector similarity search with BM25 keyword search via RRF."""

    def __init__(
        self,
        vector_store: VectorStorePort,
        vector_weight: float = VECTOR_WEIGHT,
        bm25_weight: float = BM25_WEIGHT,
        rrf_k: int = RRF_K,
    ):
        self._vector_store = vector_store
        self._vector_weight = vector_weight
        self._bm25_weight = bm25_weight
        self._rrf_k = rrf_k
        self._bm25_docs: list[Document] | None = None

    def _get_bm25_docs(self) -> list[Document]:
        if self._bm25_docs is None:
            all_data = self._vector_store.get(include=["documents", "metadatas"])
            docs = []
            for content, metadata in zip(
                all_data.get("documents", []),
                all_data.get("metadatas", []),
            ):
                if content:
                    docs.append(Document(page_content=content, metadata=metadata or {}))
            self._bm25_docs = docs
        return self._bm25_docs

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[Document],
        bm25_results: list[Document],
    ) -> list[tuple[Document, float]]:
        scores: dict[str, float] = defaultdict(float)
        doc_map: dict[str, Document] = {}

        for rank, doc in enumerate(vector_results):
            key = doc.page_content[:300]
            scores[key] += self._vector_weight * (1.0 / (self._rrf_k + rank + 1))
            doc_map[key] = doc

        for rank, doc in enumerate(bm25_results):
            key = doc.page_content[:300]
            scores[key] += self._bm25_weight * (1.0 / (self._rrf_k + rank + 1))
            if key not in doc_map:
                doc_map[key] = doc

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [(doc_map[key], score) for key, score in ranked]

    def search(
        self,
        query: str,
        num_results: int = 5,
        filter_dict: dict | None = None,
    ) -> list[dict]:
        """Perform hybrid search combining vector + BM25."""
        fetch_k = min(num_results * 2, 20)
        vector_results = self._vector_store.similarity_search(
            query=query, k=fetch_k, filter=filter_dict,
        )

        bm25_docs = self._get_bm25_docs()
        bm25_results: list[Document] = []

        if bm25_docs:
            if filter_dict:
                allowed_companies: set[str] = set()
                for cond in filter_dict.get("$or", []):
                    if "company" in cond:
                        allowed_companies.add(cond["company"])
                filtered_docs = (
                    [d for d in bm25_docs if d.metadata.get("company", "") in allowed_companies]
                    if allowed_companies
                    else bm25_docs
                )
            else:
                filtered_docs = bm25_docs

            if not filtered_docs:
                filtered_docs = bm25_docs

            bm25_retriever = BM25Retriever.from_documents(filtered_docs, k=fetch_k)
            bm25_results = bm25_retriever.invoke(query)

        if bm25_results:
            fused = self._reciprocal_rank_fusion(vector_results, bm25_results)
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
