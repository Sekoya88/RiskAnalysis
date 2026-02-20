"""
Agent State Schema — Defines the typed state that flows through the
LangGraph multi-agent workflow.

Uses LangGraph's `Annotated` message reducer pattern for automatic
message accumulation across nodes.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Literal, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Global state shared across all agent nodes in the LangGraph.

    Attributes:
        messages: Accumulated conversation messages (auto-merged via add_messages).
        next_agent: The next agent to route to, set by the supervisor.
        current_company: The company / entity currently being analyzed.
        risk_signals: Intermediate risk signals collected by individual agents.
        final_report: The synthesized final risk assessment report.
        iteration_count: Guard counter to prevent infinite loops.
    """

    # ── Core message stream (auto-accumulating) ──────────────────────
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # ── Routing ──────────────────────────────────────────────────────
    next_agent: str

    # ── Analysis context ─────────────────────────────────────────────
    current_company: str
    risk_signals: Annotated[list[dict], operator.add]

    # ── Output ───────────────────────────────────────────────────────
    final_report: str

    # ── Safety guard ─────────────────────────────────────────────────
    iteration_count: int
