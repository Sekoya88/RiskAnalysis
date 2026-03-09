"""Infrastructure — Redis checkpointer adapter."""

from __future__ import annotations

import os


def get_redis_checkpointer():
    """Return an AsyncRedisSaver context manager for LangGraph state persistence.

    Usage:
        async with get_redis_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    from langgraph.checkpoint.redis import AsyncRedisSaver

    return AsyncRedisSaver.from_conn_string(redis_url)
