"""Infrastructure — HuggingFace Embedding adapter (fallback).

Kept as a fallback option if Ollama embedding is not available.
"""

from __future__ import annotations

from langchain_huggingface import HuggingFaceEmbeddings


class HuggingFaceEmbeddingAdapter:
    """EmbeddingPort implementation backed by HuggingFace sentence-transformers.

    Runs locally on CPU. No API key required.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
    ):
        self._embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)
