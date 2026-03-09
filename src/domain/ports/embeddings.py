"""Port — Embedding model abstraction (Protocol)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingPort(Protocol):
    """Abstract interface for embedding providers.

    Implementations: OllamaEmbeddingAdapter, HuggingFaceEmbeddingAdapter.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        ...
