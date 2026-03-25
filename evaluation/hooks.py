"""
Optional hooks — keep API surface minimal.

Patterns:
- Pass trace_sink=RunTraceCollector() directly to run_analysis (preferred).
- Use fastapi_analyze_with_trace() wrapper if you inject tracing from middleware.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from evaluation.collector import RunTraceCollector

T = TypeVar("T")


def attach_collector_to_analyze(
    analyze_coro: Callable[..., Awaitable[T]],
    collector: RunTraceCollector,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Merge trace_sink into kwargs for any coroutine that forwards **kwargs to run_analysis.

    Example:
        kwargs = attach_collector_to_analyze(run_analysis, collector, query="...", use_redis=False)
        await run_analysis(**kwargs)
    """
    out = {**kwargs, "trace_sink": collector}
    return out


async def traced_run_analysis(
    collector: RunTraceCollector,
    query: str,
    use_redis: bool = False,
    thread_id: str | None = None,
):
    """Thin wrapper around src.main.run_analysis with a collector."""
    from src.main import run_analysis

    return await run_analysis(
        query=query,
        use_redis=use_redis,
        thread_id=thread_id,
        trace_sink=collector,
    )
