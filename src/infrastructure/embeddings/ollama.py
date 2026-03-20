"""Infrastructure — Ollama Embedding adapter (embeddinggemma).

Uses the Ollama /api/embed endpoint via langchain-ollama.
Replaces HuggingFace sentence-transformers, removing ~2GB of dependencies.
"""

from __future__ import annotations

import os

from langchain_ollama import OllamaEmbeddings


class OllamaEmbeddingAdapter:
    """EmbeddingPort implementation backed by Ollama (embeddinggemma).

    Runs locally via the same Ollama instance used for LLM inference.
    Model: embeddinggemma (300M params, Google Gemma 3 architecture, 100+ languages).

    Prerequisites:
        ollama pull embeddinggemma
    """

    def __init__(
        self,
        model: str = "embeddinggemma",
        base_url: str | None = None,
    ):
        base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._embeddings = OllamaEmbeddings(
            model=model,
            base_url=base_url,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)
