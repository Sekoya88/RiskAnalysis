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


async def build_graph_with_redis() -> Any:
    """Build the graph with Redis-backed state persistence.

    Uses langgraph-checkpoint-redis for fault-tolerant, highly concurrent
    state management with sub-second latency.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    try:
        from langgraph.checkpoint.redis import AsyncRedisSaver

        async with AsyncRedisSaver.from_conn_string(redis_url) as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            return graph, checkpointer
    except ImportError:
        print("⚠️  langgraph-checkpoint-redis not available. Using in-memory state.")
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        graph = build_graph(checkpointer=checkpointer)
        return graph, checkpointer
    except Exception as e:
        print(f"⚠️  Redis connection failed ({e}). Falling back to in-memory state.")
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        graph = build_graph(checkpointer=checkpointer)
        return graph, checkpointer
