"""
LangGraph Builder — Constructs the multi-agent StateGraph with
conditional routing, Redis checkpointing, and async execution.

Graph topology:
  ┌──────────┐
  │ Supervisor│ ◄──────────────────────────────────┐
  └────┬─────┘                                     │
       │ routes to                                  │
       ├──► geopolitical_analyst ──► Supervisor ────┤
       ├──► credit_evaluator     ──► Supervisor ────┤
       ├──► market_synthesizer   ──► Supervisor ────┤
       └──► FINISH (END)                            │
                                                    │
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from src.agents.nodes import (
    credit_evaluator_node,
    geopolitical_analyst_node,
    market_synthesizer_node,
)
from src.agents.supervisor import supervisor_node
from src.state.schema import AgentState

load_dotenv()


def _route_supervisor(state: AgentState) -> str:
    """Conditional edge: routes based on the supervisor's decision."""
    next_agent = state.get("next_agent", "FINISH")
    if next_agent == "FINISH":
        return "end"
    return next_agent


def build_graph(checkpointer=None) -> Any:
    """Build and compile the multi-agent LangGraph.

    Args:
        checkpointer: Optional LangGraph checkpointer (e.g., AsyncRedisSaver)
                      for persistent state management.

    Returns:
        Compiled LangGraph ready for invocation.
    """
    # ── Define the StateGraph ─────────────────────────────────────────
    workflow = StateGraph(AgentState)

    # ── Add nodes ─────────────────────────────────────────────────────
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("geopolitical_analyst", geopolitical_analyst_node)
    workflow.add_node("credit_evaluator", credit_evaluator_node)
    workflow.add_node("market_synthesizer", market_synthesizer_node)

    # ── Set entry point ───────────────────────────────────────────────
    workflow.set_entry_point("supervisor")

    # ── Add conditional edges from supervisor ─────────────────────────
    workflow.add_conditional_edges(
        "supervisor",
        _route_supervisor,
        {
            "geopolitical_analyst": "geopolitical_analyst",
            "credit_evaluator": "credit_evaluator",
            "market_synthesizer": "market_synthesizer",
            "end": END,
        },
    )

    # ── All agents report back to supervisor ──────────────────────────
    workflow.add_edge("geopolitical_analyst", "supervisor")
    workflow.add_edge("credit_evaluator", "supervisor")
    workflow.add_edge("market_synthesizer", "supervisor")

    # ── Compile ───────────────────────────────────────────────────────
    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    graph = workflow.compile(**compile_kwargs)
    return graph


def get_redis_checkpointer():
    """Return an AsyncRedisSaver context manager for Redis-backed persistence.

    Usage:
        async with get_redis_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            # ... use graph inside this block ...

    Raises ImportError if langgraph-checkpoint-redis is not installed.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    from langgraph.checkpoint.redis import AsyncRedisSaver
    return AsyncRedisSaver.from_conn_string(redis_url)
