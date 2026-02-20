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
def _get_llm(temperature: float = 0.1) -> ChatGoogleGenerativeAI:
    """Instantiate Gemini 2.0 Flash via langchain-google-genai."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=temperature,
        max_output_tokens=8192,
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


async def _run_react_loop(
    llm_with_tools: Any,
    system_prompt: str,
    state_messages: list,
    max_iterations: int = 6,
) -> str:
    """Run the ReAct reasoning loop with retry on rate limits.

    Thought → Action → Observation → ... → Final Answer

    Returns:
        The final text content from the agent.
    """
    messages = [SystemMessage(content=system_prompt)] + list(state_messages)

    response = None
    for iteration in range(max_iterations):
        # Invoke LLM with retry on rate limits
        response = await retry_with_backoff(
            llm_with_tools.ainvoke,
            messages,
            max_retries=5,
            base_delay=15.0,
        )
        messages.append(response)

        # If no tool calls, the agent has finished reasoning
        if not response.tool_calls:
            break

        # Execute tool calls
        tool_messages = await _execute_tool_calls(response.tool_calls)
        messages.extend(tool_messages)

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

    return final_text if final_text.strip() else "Analysis could not be completed."


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
    print("   🌍 Geopolitical Analyst starting analysis...")
    llm = _get_llm(temperature=0.2)
    llm_with_tools = llm.bind_tools(GEOPOLITICAL_TOOLS)

    final_content = await _run_react_loop(
        llm_with_tools=llm_with_tools,
        system_prompt=GEOPOLITICAL_ANALYST_PROMPT,
        state_messages=state["messages"],
        max_iterations=6,
    )

    print("   ✅ Geopolitical Analyst completed.")
    return {
        "messages": [AIMessage(content=f"[GEOPOLITICAL ANALYST]\n\n{final_content}", name="geopolitical_analyst")],
        "risk_signals": [{"agent": "geopolitical_analyst", "analysis": final_content}],
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


# ── Agent node: Credit Risk Evaluator ─────────────────────────────────
async def credit_evaluator_node(state: AgentState) -> dict[str, Any]:
    """Credit Risk Evaluator agent — performs fundamental credit analysis."""
    print("   💳 Credit Risk Evaluator starting analysis...")
    llm = _get_llm(temperature=0.1)
    llm_with_tools = llm.bind_tools(CREDIT_TOOLS)

    final_content = await _run_react_loop(
        llm_with_tools=llm_with_tools,
        system_prompt=CREDIT_RISK_EVALUATOR_PROMPT,
        state_messages=state["messages"],
        max_iterations=6,
    )

    print("   ✅ Credit Risk Evaluator completed.")
    return {
        "messages": [AIMessage(content=f"[CREDIT RISK EVALUATOR]\n\n{final_content}", name="credit_evaluator")],
        "risk_signals": [{"agent": "credit_evaluator", "analysis": final_content}],
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


# ── Agent node: Market Synthesizer ────────────────────────────────────
async def market_synthesizer_node(state: AgentState) -> dict[str, Any]:
    """Market Synthesizer agent — produces the final integrated risk report."""
    print("   📊 Market Synthesizer starting synthesis...")
    llm = _get_llm(temperature=0.15)
    llm_with_tools = llm.bind_tools(SYNTHESIZER_TOOLS)

    # Inject today's date into the prompt
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    formatted_prompt = MARKET_SYNTHESIZER_PROMPT.format(today=today)

    final_content = await _run_react_loop(
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

    print("   ✅ Market Synthesizer completed.")
    return {
        "messages": [AIMessage(content=f"[MARKET SYNTHESIZER]\n\n{final_content}", name="market_synthesizer")],
        "risk_signals": [{"agent": "market_synthesizer", "analysis": final_content}],
        "final_report": final_content,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }

