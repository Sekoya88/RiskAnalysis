"""Infrastructure — Embedding Factory.

Creates the appropriate embedding adapter based on configuration.
"""

from __future__ import annotations

from src.domain.ports.embeddings import EmbeddingPort
from src.infrastructure.config.providers import get_embedding_config


def create_embeddings(provider: str | None = None) -> EmbeddingPort:
    """Factory: create the right embedding adapter.

    Args:
        provider: "ollama" or "huggingface". If None, reads from config.

    Returns:
        An object satisfying EmbeddingPort.
    """
    config = get_embedding_config()
    provider = provider or config.get("default", "ollama")

    if provider == "huggingface":
        from src.infrastructure.embeddings.huggingface import HuggingFaceEmbeddingAdapter

        hf_config = config.get("providers", {}).get("huggingface", {})
        return HuggingFaceEmbeddingAdapter(
            model_name=hf_config.get("model", "all-MiniLM-L6-v2"),
            device=hf_config.get("device", "cpu"),
        )

    # Default: Ollama embeddinggemma
    from src.infrastructure.embeddings.ollama import OllamaEmbeddingAdapter

    ollama_config = config.get("providers", {}).get("ollama", {})
    return OllamaEmbeddingAdapter(
        model=ollama_config.get("model", "embeddinggemma"),
        base_url=ollama_config.get("base_url"),
    )
