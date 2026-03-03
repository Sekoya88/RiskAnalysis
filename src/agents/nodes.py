"""
Agent Nodes — LangGraph node functions for each specialized agent.

Each node:
  1. Binds its tools to the LLM (Google Gemini via langchain-google-genai).
  2. Invokes the LLM with its specialist system prompt.
  3. Implements ReAct tool-use loop with exponential backoff retry.
  4. Returns an updated AgentState with new messages and risk signals.
"""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agents.prompts import (
    CREDIT_RISK_EVALUATOR_PROMPT,
    GEOPOLITICAL_ANALYST_PROMPT,
    MARKET_SYNTHESIZER_PROMPT,
)
from src.state.schema import AgentState
from src.tools.market_data import get_market_data
from src.tools.news_api import search_geopolitical_news, search_web_general
from src.tools.rag_pipeline import search_corporate_disclosures
from src.utils import retry_with_backoff

load_dotenv()

# ── LLM Configuration ────────────────────────────────────────────────
def _get_llm(temperature: float = 0.1, max_output_tokens: int = 8192) -> ChatGoogleGenerativeAI:
    """Instantiate Gemini 2.5 Flash via langchain-google-genai."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=temperature,
        max_output_tokens=max_output_tokens,
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


async def _execute_tool_calls(tool_calls: list[dict]) -> list[ToolMessage]:
    """Execute tool calls and return ToolMessages."""
    messages = []
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_fn = TOOL_REGISTRY.get(tool_name)

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
            # Keep only the final named summary (e.g. [GEOPOLITICAL ANALYST])
            pruned.append(AIMessage(content=msg.content, name=msg.name))
        # Drop: ToolMessages, unnamed AIMessages (tool-calling intermediaries)
    return pruned


def _extract_token_usage(response) -> dict:
    """Extract token usage from a Gemini LLM response.

    LangChain / Gemini can expose usage_metadata in multiple locations:
      1. response.usage_metadata  (dict or object)
      2. response.response_metadata["usage_metadata"]
    """
    usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}
    try:
        um = None
        # Method 1: Direct attribute (LangChain >=0.2)
        raw_um = getattr(response, "usage_metadata", None)
        if raw_um:
            if isinstance(raw_um, dict):
                um = raw_um
            else:
                # Object with attributes
                um = {
                    "prompt_token_count": getattr(raw_um, "input_tokens", 0) or getattr(raw_um, "prompt_token_count", 0),
                    "candidates_token_count": getattr(raw_um, "output_tokens", 0) or getattr(raw_um, "candidates_token_count", 0),
                    "cached_content_token_count": getattr(raw_um, "cached_content_token_count", 0),
                }

        # Method 2: Nested in response_metadata
        if not um or all(v == 0 for v in um.values() if isinstance(v, (int, float))):
            meta = getattr(response, "response_metadata", {}) or {}
            um2 = meta.get("usage_metadata", {})
            if um2:
                um = um2

        if um:
            # LangChain uses input_tokens/output_tokens; Gemini uses prompt_token_count/candidates_token_count
            usage["input_tokens"] = (
                um.get("input_tokens", 0) or um.get("prompt_token_count", 0)
            )
            usage["output_tokens"] = (
                um.get("output_tokens", 0) or um.get("candidates_token_count", 0)
            )
            usage["cached_tokens"] = um.get("cached_content_token_count", 0)

        # Fallback for Gemini/LangChain glitch: sometimes output_tokens is 0 despite having content
        if usage["output_tokens"] == 0 and hasattr(response, "content") and response.content:
            content_str = str(response.content)
            # Rough approximation: 1 token ~= 4 characters
            usage["output_tokens"] = len(content_str) // 4
    except Exception:
        pass
    return usage


# ── Shared log queue for live UI streaming ────────────────────────────
import queue
_log_queue: queue.Queue | None = None


def set_log_queue(q: queue.Queue):
    """Set the shared log queue (called from Streamlit UI thread)."""
    global _log_queue
    _log_queue = q


def _emit_log(message: str):
    """Push a log message to the shared queue (if set)."""
    if _log_queue is not None:
        try:
            _log_queue.put_nowait(message)
        except queue.Full:
            pass
    print(f"   {message}")


async def _run_react_loop(
    llm_with_tools: Any,
    system_prompt: str,
    state_messages: list,
    max_iterations: int = 6,
) -> tuple[str, list, list[dict]]:
    """Run the ReAct reasoning loop with retry on rate limits.

    Thought → Action → Observation → ... → Final Answer

    Returns:
        A tuple of (final_text, messages_to_add, token_records).
        final_text: The final reasoning result.
        messages_to_add: All AI and Tool messages generated during the loop.
        token_records: List of token usage dicts per LLM call.
    """
    messages = [SystemMessage(content=system_prompt)] + list(state_messages)
    loop_messages = []
    token_records = []

    response = None
    for iteration in range(max_iterations):
        _emit_log(f"💭 Iteration {iteration + 1}/{max_iterations} — thinking...")
        # Invoke LLM with retry on rate limits
        response = await retry_with_backoff(
            llm_with_tools.ainvoke,
            messages,
            max_retries=5,
            base_delay=15.0,
        )
        messages.append(response)
        loop_messages.append(response)

        # Track token usage
        tu = _extract_token_usage(response)
        token_records.append(tu)
        if tu["input_tokens"] > 0:
            _emit_log(f"📊 Tokens: {tu['input_tokens']:,} in / {tu['output_tokens']:,} out")

        # If no tool calls, the agent has finished reasoning
        if not response.tool_calls:
            _emit_log("✍️ Generating final response...")
            break

        # Execute tool calls
        for tc in response.tool_calls:
            _emit_log(f"🔧 Calling tool: {tc['name']}")
        tool_messages = await _execute_tool_calls(response.tool_calls)
        messages.extend(tool_messages)
        loop_messages.extend(tool_messages)

    # Extract text from the final response
    final_text = _extract_text(response.content) if response else ""

    # Fallback: if Gemini thinking mode returned empty text in the last
    # response, scan backwards through messages for the last substantive
    # AI text (skipping tool-call-only and system messages).
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
        token_records,
    )


def _extract_text(content: Any) -> str:
    """Extract plain text from Gemini's structured content format.

    Gemini 2.5 Flash may return content as:
      - A plain string
      - A list of dicts with 'type' keys: 'text', 'thinking', etc.
    This normalizes to a plain string, keeping only 'text' blocks.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                # Only keep explicit text blocks, skip thinking/signature
                if block.get("type") == "text":
                    text = block.get("text", "")
                    if text.strip():  # skip empty text blocks
                        parts.append(text)
            elif isinstance(block, str):
                if block.strip():
                    parts.append(block)
        return "\n".join(parts)
    return str(content)


# ── Agent node: Geopolitical Analyst ──────────────────────────────────
async def geopolitical_analyst_node(state: AgentState) -> dict[str, Any]:
    """Geopolitical Analyst agent — assesses macro and geopolitical risks."""
    _emit_log("🌍 Geopolitical Analyst starting...")
    llm = _get_llm(temperature=0.2, max_output_tokens=4096)
    llm_with_tools = llm.bind_tools(GEOPOLITICAL_TOOLS)

    final_content, new_messages, tokens = await _run_react_loop(
        llm_with_tools=llm_with_tools,
        system_prompt=GEOPOLITICAL_ANALYST_PROMPT,
        state_messages=state["messages"],
        max_iterations=6,
    )

    total_in = sum(t["input_tokens"] for t in tokens)
    total_out = sum(t["output_tokens"] for t in tokens)
    total_cached = sum(t["cached_tokens"] for t in tokens)
    _emit_log(f"✅ Geopolitical done — {total_in:,} in / {total_out:,} out")
    return {
        "messages": [AIMessage(content=f"[GEOPOLITICAL ANALYST]\n\n{final_content}", name="geopolitical_analyst")] + new_messages,
        "risk_signals": [{"agent": "geopolitical_analyst", "analysis": final_content}],
        "iteration_count": state.get("iteration_count", 0) + 1,
        "token_usage": [{"agent": "geopolitical_analyst", "input": total_in, "output": total_out, "cached": total_cached}],
    }


# ── Agent node: Credit Risk Evaluator ─────────────────────────────────
async def credit_evaluator_node(state: AgentState) -> dict[str, Any]:
    """Credit Risk Evaluator agent — performs fundamental credit analysis."""
    _emit_log("💳 Credit Evaluator starting...")
    llm = _get_llm(temperature=0.1, max_output_tokens=4096)
    llm_with_tools = llm.bind_tools(CREDIT_TOOLS)

    final_content, new_messages, tokens = await _run_react_loop(
        llm_with_tools=llm_with_tools,
        system_prompt=CREDIT_RISK_EVALUATOR_PROMPT,
        state_messages=state["messages"],
        max_iterations=6,
    )

    total_in = sum(t["input_tokens"] for t in tokens)
    total_out = sum(t["output_tokens"] for t in tokens)
    total_cached = sum(t["cached_tokens"] for t in tokens)
    _emit_log(f"✅ Credit Evaluator done — {total_in:,} in / {total_out:,} out")
    return {
        "messages": [AIMessage(content=f"[CREDIT RISK EVALUATOR]\n\n{final_content}", name="credit_evaluator")] + new_messages,
        "risk_signals": [{"agent": "credit_evaluator", "analysis": final_content}],
        "iteration_count": state.get("iteration_count", 0) + 1,
        "token_usage": [{"agent": "credit_evaluator", "input": total_in, "output": total_out, "cached": total_cached}],
    }


# ── Agent node: Market Synthesizer ────────────────────────────────────
async def market_synthesizer_node(state: AgentState) -> dict[str, Any]:
    """Market Synthesizer agent — produces the final integrated risk report."""
    _emit_log("📊 Market Synthesizer starting...")
    llm = _get_llm(temperature=0.15, max_output_tokens=8192)
    llm_with_tools = llm.bind_tools(SYNTHESIZER_TOOLS)

    # Inject today's date into the prompt
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    formatted_prompt = MARKET_SYNTHESIZER_PROMPT.format(today=today)

    final_content, new_messages, tokens = await _run_react_loop(
        llm_with_tools=llm_with_tools,
        system_prompt=formatted_prompt,
        state_messages=state["messages"],
        max_iterations=4,
    )

    # Strip any LLM preamble before the structured report
    report_marker = "═══"
    if report_marker in final_content:
        idx = final_content.index(report_marker)
        final_content = final_content[idx:]

    total_in = sum(t["input_tokens"] for t in tokens)
    total_out = sum(t["output_tokens"] for t in tokens)
    total_cached = sum(t["cached_tokens"] for t in tokens)
    _emit_log(f"✅ Synthesizer done — {total_in:,} in / {total_out:,} out")
    return {
        "messages": [AIMessage(content=f"[MARKET SYNTHESIZER]\n\n{final_content}", name="market_synthesizer")] + new_messages,
        "risk_signals": [{"agent": "market_synthesizer", "analysis": final_content}],
        "final_report": final_content,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "token_usage": [{"agent": "market_synthesizer", "input": total_in, "output": total_out, "cached": total_cached}],
    }

