"""
Infrastructure — Langfuse observability adapter.

Uses a custom callback (LangfuseV2Callback) that sends directly to
/api/public/ingestion, compatible with Langfuse server v2.x OSS.

Background:
- Langfuse SDK v3/v4 sends via OTEL → /api/public/otel/v1/traces (404 on server v2)
- Langfuse SDK v2 requires langchain.callbacks which was removed in langchain 1.x
- Solution: custom LangChain BaseCallbackHandler + direct HTTP to /api/public/ingestion

Env vars:
    LANGFUSE_PUBLIC_KEY=pk-lf-...
    LANGFUSE_SECRET_KEY=sk-lf-...
    LANGFUSE_HOST=http://localhost:3001
"""

from __future__ import annotations

import os
from typing import Any


def get_langfuse_handler(session_id: str | None = None) -> Any | None:
    """
    Return a LangfuseV2Callback if keys are configured, else None.
    """
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    host = os.getenv("LANGFUSE_HOST", "http://localhost:3001")

    if not public_key or public_key.startswith("<"):
        return None

    try:
        from src.infrastructure.observability.langfuse_callback import LangfuseV2Callback
        return LangfuseV2Callback(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            session_id=session_id,
        )
    except Exception as e:
        from loguru import logger
        logger.warning(f"Langfuse handler could not be created: {e}")
        return None


def build_langfuse_config(
    base_config: dict,
    session_id: str | None = None,
    handler: Any | None = None,
    model: str | None = None,  # kept for API compat, unused
) -> dict:
    """
    Merge Langfuse callback into the LangGraph run config.
    """
    config = dict(base_config)
    if handler is None:
        return config
    config["callbacks"] = [handler]
    return config


def shutdown_langfuse() -> None:
    """No-op for custom callback (synchronous sends)."""
    pass
