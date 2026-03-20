"""Application — Geopolitical Analyst agent node."""

from __future__ import annotations

import queue
from typing import Any

from langchain_core.messages import AIMessage

from src.agents.middleware import AgentMiddleware
from src.application.agents.base import run_react_loop
from src.application.dto import AgentState
from src.infrastructure.llm.factory import create_llm
from src.infrastructure.skills.loader import get_skill_prompt

# Populated by container
_log_queue: queue.Queue | None = None
_tools: list[Any] = []


def configure(tools: list[Any], log_queue: queue.Queue | None = None) -> None:
    global _log_queue, _tools
    _log_queue = log_queue
    _tools = tools


async def geopolitical_analyst_node(state: AgentState) -> dict[str, Any]:
    """Geopolitical Analyst — assesses macro and geopolitical risks."""
    mw = AgentMiddleware(agent_name="geopolitical_analyst", log_queue=_log_queue)
    mw.on_start("Geopolitical Analyst")

    llm = create_llm(temperature=0.2, num_predict=4096)
    llm_with_tools = llm.bind_tools(_tools)

    final_content, new_messages, _ = await run_react_loop(
        llm_with_tools=llm_with_tools,
        system_prompt=get_skill_prompt("geopolitical-analyst"),
        state_messages=state["messages"],
        mw=mw,
        max_iterations=6,
    )

    mw.on_done()
    s = mw.summary()
    return {
        "messages": [AIMessage(content=f"[GEOPOLITICAL ANALYST]\n\n{final_content}", name="geopolitical_analyst")] + new_messages,
        "risk_signals": [{"agent": "geopolitical_analyst", "analysis": final_content}],
        "iteration_count": state.get("iteration_count", 0) + 1,
        "token_usage": [{"agent": s["agent"], "input": s["input"], "output": s["output"], "cached": s["cached"]}],
    }
