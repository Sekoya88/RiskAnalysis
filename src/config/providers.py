"""
Backward-compatible shim — re-exports from new DDD locations.
"""

from src.infrastructure.config.providers import (
    get_provider_config,
    get_model_config,
    get_embedding_config,
    get_vector_store_config,
    get_retrieval_config,
)

__all__ = [
    "get_provider_config",
    "get_model_config",
    "get_embedding_config",
    "get_vector_store_config",
    "get_retrieval_config",
]
