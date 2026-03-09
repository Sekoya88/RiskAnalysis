"""
Application — LangGraph StateGraph builder.

Composes the multi-agent workflow with conditional routing.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from src.application.dto import AgentState
from src.application.agents.geopolitical import geopolitical_analyst_node
from src.application.agents.credit import credit_evaluator_node
from src.application.agents.synthesizer import market_synthesizer_node
from src.application.supervisor import supervisor_node


def _route_supervisor(state: AgentState) -> str:
    next_agent = state.get("next_agent", "FINISH")
    if next_agent == "FINISH":
        return "end"
    return next_agent


def build_graph(checkpointer=None) -> Any:
    """Build and compile the multi-agent LangGraph."""
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("geopolitical_analyst", geopolitical_analyst_node)
    workflow.add_node("credit_evaluator", credit_evaluator_node)
    workflow.add_node("market_synthesizer", market_synthesizer_node)

    workflow.set_entry_point("supervisor")

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

    workflow.add_edge("geopolitical_analyst", "supervisor")
    workflow.add_edge("credit_evaluator", "supervisor")
    workflow.add_edge("market_synthesizer", "supervisor")

    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    return workflow.compile(**compile_kwargs)
