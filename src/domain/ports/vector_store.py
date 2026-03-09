"""Port — Vector store abstraction (Protocol)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VectorStorePort(Protocol):
    """Abstract interface for vector stores.

    Implementations: ChromaVectorStoreAdapter.
    """

    def similarity_search(self, query: str, k: int = 5, filter: dict | None = None) -> list[Any]:
        ...

    def add_documents(self, documents: list[Any]) -> None:
        ...

    def get(self, include: list[str] | None = None) -> dict:
        ...
