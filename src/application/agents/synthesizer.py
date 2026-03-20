"""Application — Market Synthesizer agent node."""

from __future__ import annotations

import queue
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage

from src.agents.middleware import AgentMiddleware
from src.application.agents.base import run_react_loop
from src.application.dto import AgentState
from src.domain.models.risk_report import parse_report_to_structured
from src.domain.services.report_builder import strip_report_preamble
from src.infrastructure.llm.factory import create_llm
from src.infrastructure.skills.loader import get_skill_prompt

_log_queue: queue.Queue | None = None
_tools: list[Any] = []
_memory_adapter: Any = None


def configure(tools: list[Any], memory_adapter: Any = None, log_queue: queue.Queue | None = None) -> None:
    global _log_queue, _tools, _memory_adapter
    _log_queue = log_queue
    _tools = tools
    _memory_adapter = memory_adapter


async def market_synthesizer_node(state: AgentState) -> dict[str, Any]:
    """Market Synthesizer — produces the final integrated risk report."""
    mw = AgentMiddleware(agent_name="market_synthesizer", log_queue=_log_queue)
    mw.on_start("Market Synthesizer")

    llm = create_llm(temperature=0.15, num_predict=8192)
    llm_with_tools = llm.bind_tools(_tools)

    today = datetime.now().strftime("%Y-%m-%d")
    formatted_prompt = get_skill_prompt("market-synthesizer", today=today)

    if _memory_adapter:
        memory = _memory_adapter.load()
        if memory.strip():
            formatted_prompt += f"\n\n## Previous Analyses (Memory)\n{memory}"

    final_content, new_messages, _ = await run_react_loop(
        llm_with_tools=llm_with_tools,
        system_prompt=formatted_prompt,
        state_messages=state["messages"],
        mw=mw,
        max_iterations=4,
    )

    final_content = strip_report_preamble(final_content)

    structured = parse_report_to_structured(final_content)
    mw.on_structured_report(structured.entity, structured.overall_score, structured.credit_rating)

    if _memory_adapter:
        _memory_adapter.update(structured.entity, structured.to_scores_dict(), today)

    mw.on_done()
    s = mw.summary()
    return {
        "messages": [AIMessage(content=f"[MARKET SYNTHESIZER]\n\n{final_content}", name="market_synthesizer")] + new_messages,
        "risk_signals": [{"agent": "market_synthesizer", "analysis": final_content}],
        "final_report": final_content,
        "structured_report": structured.model_dump(),
        "iteration_count": state.get("iteration_count", 0) + 1,
        "token_usage": [{"agent": s["agent"], "input": s["input"], "output": s["output"], "cached": s["cached"]}],
    }
