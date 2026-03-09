"""
Agent Nodes — LangGraph node functions for each specialized agent.

Each node:
  1. Binds its tools to the LLM (Ollama via langchain-ollama).
  2. Loads its specialist skill (SKILL.md) for the system prompt.
  3. Implements ReAct tool-use loop with exponential backoff retry.
  4. Uses AgentMiddleware for logging & token tracking.
  5. Returns an updated AgentState with new messages and risk signals.
"""

from __future__ import annotations

import json
import os
import queue
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None

from loguru import logger

from src.agents.memory import load_memory, update_memory
from src.agents.middleware import AgentMiddleware
from src.agents.skills import get_skill_prompt
from src.config.providers import get_model_config
from src.state.schema import AgentState, parse_report_to_structured
from src.tools.market_data import get_market_data
from src.tools.news_api import search_geopolitical_news, search_web_general
from src.tools.rag_pipeline import search_corporate_disclosures
from src.utils import retry_with_backoff

load_dotenv()

# ── LLM Configuration ────────────────────────────────────────────────
def _get_llm(temperature: float | None = None, num_predict: int | None = None) -> Any:
    """Instantiate a local LLM via Ollama or Google Gemini."""
    model = os.getenv("OLLAMA_MODEL", "qwen3.5")

    if model.startswith("gemini"):
        if not ChatGoogleGenerativeAI:
            raise ImportError("langchain-google-genai is not installed. Please install it to use Gemini models.")
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required to use Gemini models.")
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature if temperature is not None else 0.1,
            max_output_tokens=num_predict if num_predict is not None else 8192,
        )

    cfg = get_model_config(model)
    return ChatOllama(
        model=model,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=temperature if temperature is not None else cfg.get("temperature", 0.1),
        num_predict=num_predict if num_predict is not None else cfg.get("num_predict", 4096),
    )


# ── Tool dispatch registry ────────────────────────────────────────────
TOOL_REGISTRY = {
    "search_geopolitical_news": search_geopolitical_news,
    "search_web_general": search_web_general,
    "search_corporate_disclosures": search_corporate_disclosures,
    "get_market_data": get_market_data,
}

# ── Tool sets per agent ───────────────────────────────────────────────
GEOPOLITICAL_TOOLS = [search_geopolitical_news, search_web_general, search_corporate_disclosures]
CREDIT_TOOLS = [get_market_data, search_corporate_disclosures, search_web_general]
SYNTHESIZER_TOOLS = [search_corporate_disclosures, search_web_general]


async def _execute_tool_calls(tool_calls: list[dict], mw: AgentMiddleware) -> list[ToolMessage]:
    """Execute tool calls and return ToolMessages."""
    messages = []
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_fn = TOOL_REGISTRY.get(tool_name)

        mw.on_tool_call(tool_name)

        if tool_fn:
            try:
                result = await tool_fn.ainvoke(tool_args)
            except Exception as e:
                result = json.dumps({"error": f"Tool {tool_name} failed: {str(e)}"})
        else:
            result = json.dumps({"error": f"Unknown tool: {tool_name}"})

        messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
    return messages


def _prune_messages(messages: list) -> list:
    """Prune messages to keep only essentials for inter-agent context.

    Drops intermediate ToolMessages and tool-calling AIMessages to reduce
    token count. Keeps: HumanMessage, named agent summaries.
    This saves ~30-50K tokens/run by not re-sending raw tool results.
    """
    pruned = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            pruned.append(msg)
        elif isinstance(msg, AIMessage) and getattr(msg, "name", None):
            pruned.append(AIMessage(content=msg.content, name=msg.name))
    return pruned


def _extract_text(content: Any) -> str:
    """Extract plain text from LLM structured content format."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text = block.get("text", "")
                    if text.strip():
                        parts.append(text)
            elif isinstance(block, str):
                if block.strip():
                    parts.append(block)
        return "\n".join(parts)
    return str(content)


# ── Shared log queue for live UI streaming ────────────────────────────
_log_queue: queue.Queue | None = None


def set_log_queue(q: queue.Queue):
    """Set the shared log queue (called from Streamlit UI thread)."""
    global _log_queue
    _log_queue = q


async def _run_react_loop(
    llm_with_tools: Any,
    system_prompt: str,
    state_messages: list,
    mw: AgentMiddleware,
    max_iterations: int = 6,
) -> tuple[str, list, list[dict]]:
    """Run the ReAct reasoning loop with retry on rate limits.

    Returns:
        A tuple of (final_text, messages_to_add, token_records).
    """
    messages = [SystemMessage(content=system_prompt)] + list(state_messages)
    loop_messages = []

    response = None
    for iteration in range(max_iterations):
        mw.on_iteration(iteration + 1, max_iterations)
        response = await retry_with_backoff(
            llm_with_tools.ainvoke,
            messages,
            max_retries=5,
            base_delay=15.0,
        )
        messages.append(response)
        loop_messages.append(response)

        mw.on_llm_response(response)

        if not response.tool_calls:
            mw.on_final_response()
            break

        tool_messages = await _execute_tool_calls(response.tool_calls, mw)
        messages.extend(tool_messages)
        loop_messages.extend(tool_messages)

    final_text = _extract_text(response.content) if response else ""

    if not final_text.strip() and len(messages) > 1:
        for msg in reversed(messages[:-1]):
            if hasattr(msg, "content") and not getattr(msg, "tool_calls", None):
                candidate = _extract_text(msg.content)
                if candidate.strip() and len(candidate.strip()) > 50:
                    final_text = candidate
                    break

    return (
        final_text if final_text.strip() else "Analysis could not be completed.",
        loop_messages,
        mw.token_records,
    )


# ── Agent node: Geopolitical Analyst ──────────────────────────────────
async def geopolitical_analyst_node(state: AgentState) -> dict[str, Any]:
    """Geopolitical Analyst agent — assesses macro and geopolitical risks."""
    mw = AgentMiddleware(agent_name="geopolitical_analyst", log_queue=_log_queue)
    mw.on_start("Geopolitical Analyst")

    llm = _get_llm(temperature=0.2, num_predict=4096)
    llm_with_tools = llm.bind_tools(GEOPOLITICAL_TOOLS)

    final_content, new_messages, _ = await _run_react_loop(
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


# ── Agent node: Credit Risk Evaluator ─────────────────────────────────
async def credit_evaluator_node(state: AgentState) -> dict[str, Any]:
    """Credit Risk Evaluator agent — performs fundamental credit analysis."""
    mw = AgentMiddleware(agent_name="credit_evaluator", log_queue=_log_queue)
    mw.on_start("Credit Evaluator")

    llm = _get_llm(temperature=0.1, num_predict=4096)
    llm_with_tools = llm.bind_tools(CREDIT_TOOLS)

    final_content, new_messages, _ = await _run_react_loop(
        llm_with_tools=llm_with_tools,
        system_prompt=get_skill_prompt("credit-evaluator"),
        state_messages=state["messages"],
        mw=mw,
        max_iterations=6,
    )

    mw.on_done()
    s = mw.summary()
    return {
        "messages": [AIMessage(content=f"[CREDIT RISK EVALUATOR]\n\n{final_content}", name="credit_evaluator")] + new_messages,
        "risk_signals": [{"agent": "credit_evaluator", "analysis": final_content}],
        "iteration_count": state.get("iteration_count", 0) + 1,
        "token_usage": [{"agent": s["agent"], "input": s["input"], "output": s["output"], "cached": s["cached"]}],
    }


# ── Agent node: Market Synthesizer ────────────────────────────────────
async def market_synthesizer_node(state: AgentState) -> dict[str, Any]:
    """Market Synthesizer agent — produces the final integrated risk report."""
    mw = AgentMiddleware(agent_name="market_synthesizer", log_queue=_log_queue)
    mw.on_start("Market Synthesizer")

    llm = _get_llm(temperature=0.15, num_predict=8192)
    llm_with_tools = llm.bind_tools(SYNTHESIZER_TOOLS)

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    formatted_prompt = get_skill_prompt("market-synthesizer", today=today)

    # Inject persistent memory (previous analyses context)
    memory = load_memory()
    if memory.strip():
        formatted_prompt += f"\n\n## Previous Analyses (Memory)\n{memory}"

    final_content, new_messages, _ = await _run_react_loop(
        llm_with_tools=llm_with_tools,
        system_prompt=formatted_prompt,
        state_messages=state["messages"],
        mw=mw,
        max_iterations=4,
    )

    # Strip any LLM preamble before the structured report
    report_marker = "═══"
    if report_marker in final_content:
        idx = final_content.index(report_marker)
        final_content = final_content[idx:]

    # Parse free-text report into structured RiskReport
    structured = parse_report_to_structured(final_content)
    mw.on_structured_report(structured.entity, structured.overall_score, structured.credit_rating)

    # Persist to memory for cross-session continuity
    update_memory(structured.entity, structured.to_scores_dict(), today)

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
