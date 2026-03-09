"""Infrastructure — Configuration loader (deepagents.toml)."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "config",
    "deepagents.toml",
)


@lru_cache(maxsize=1)
def _load_config() -> dict[str, Any]:
    if not os.path.isfile(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def get_provider_config(provider: str = "ollama") -> dict[str, Any]:
    config = _load_config()
    return config.get("models", {}).get("providers", {}).get(provider, {})


def get_model_config(model_name: str | None = None, provider: str = "ollama") -> dict[str, Any]:
    model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3.5")
    provider_config = get_provider_config(provider)
    params = dict(provider_config.get("params", {}))

    for key in list(params.keys()):
        if isinstance(params[key], dict):
            del params[key]

    model_overrides = provider_config.get("params", {}).get(model_name, {})
    params.update(model_overrides)
    return params


def get_embedding_config() -> dict[str, Any]:
    """Get embedding configuration from deepagents.toml."""
    config = _load_config()
    return config.get("embeddings", {})


def get_vector_store_config() -> dict[str, Any]:
    """Get vector store configuration from deepagents.toml."""
    config = _load_config()
    return config.get("vector_store", {})


def get_retrieval_config() -> dict[str, Any]:
    """Get retrieval configuration from deepagents.toml."""
    config = _load_config()
    return config.get("retrieval", {})
