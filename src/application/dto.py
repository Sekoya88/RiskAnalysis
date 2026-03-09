"""
Application — Data Transfer Objects for analysis requests and results.
"""

from __future__ import annotations

import operator
from typing import Annotated, Optional, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Global state flowing through the LangGraph multi-agent workflow."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_agent: str
    current_company: str
    risk_signals: Annotated[list[dict], operator.add]
    final_report: str
    structured_report: Optional[dict]
    iteration_count: int
    token_usage: Annotated[list[dict], operator.add]
