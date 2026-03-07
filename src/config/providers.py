"""
Provider Configuration — Reads deepagents.toml for per-model Ollama overrides.

Supports the DeepAgents per-model override pattern:
  - Provider-level defaults apply to all models
  - Model-level params override provider defaults (shallow merge)
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # Python < 3.11 fallback

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config", "deepagents.toml",
)


@lru_cache(maxsize=1)
def _load_config() -> dict[str, Any]:
    """Load and cache the deepagents.toml configuration."""
    if not os.path.isfile(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def get_provider_config(provider: str = "ollama") -> dict[str, Any]:
    """Get the full provider configuration block."""
    config = _load_config()
    return config.get("models", {}).get("providers", {}).get(provider, {})


def get_model_config(model_name: str | None = None, provider: str = "ollama") -> dict[str, Any]:
    """Get merged configuration for a specific model.

    Applies shallow merge: model-level params override provider-level defaults.

    Args:
        model_name: Model identifier (e.g., "qwen3.5:9b"). If None, reads OLLAMA_MODEL env.
        provider: Provider name (default: "ollama").

    Returns:
        Dict with merged params (temperature, num_ctx, num_predict, etc.).
    """
    model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
    provider_config = get_provider_config(provider)
    params = dict(provider_config.get("params", {}))

    # Remove model-specific sub-tables from base params
    for key in list(params.keys()):
        if isinstance(params[key], dict):
            del params[key]

    # Shallow merge model-specific overrides
    model_overrides = provider_config.get("params", {}).get(model_name, {})
    params.update(model_overrides)

    return params
