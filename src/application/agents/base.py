"""
Application — Base agent with ReAct loop.

Shared logic for all specialist agents: LLM invocation, tool execution,
message management, middleware hooks.
"""

from __future__ import annotations

import json
import queue
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.agents.middleware import AgentMiddleware
from src.domain.services.report_builder import extract_text
from src.utils import retry_with_backoff


# ── Tool dispatch (populated by container) ──────────────────────────
TOOL_REGISTRY: dict[str, Any] = {}


def register_tools(tools: dict[str, Any]) -> None:
    """Register tool functions in the global registry."""
    TOOL_REGISTRY.update(tools)


async def execute_tool_calls(tool_calls: list[dict], mw: AgentMiddleware) -> list[ToolMessage]:
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


def prune_messages(messages: list) -> list:
    """Keep only essential messages for inter-agent context."""
    pruned = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            pruned.append(msg)
        elif isinstance(msg, AIMessage) and getattr(msg, "name", None):
            pruned.append(AIMessage(content=msg.content, name=msg.name))
    return pruned


async def run_react_loop(
    llm_with_tools: Any,
    system_prompt: str,
    state_messages: list,
    mw: AgentMiddleware,
    max_iterations: int = 6,
) -> tuple[str, list, list[dict]]:
    """Run the ReAct reasoning loop with retry on rate limits."""
    messages = [SystemMessage(content=system_prompt)] + list(state_messages)
    loop_messages: list[Any] = []

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

        tool_messages = await execute_tool_calls(response.tool_calls, mw)
        messages.extend(tool_messages)
        loop_messages.extend(tool_messages)

    final_text = extract_text(response.content) if response else ""

    if not final_text.strip() and len(messages) > 1:
        for msg in reversed(messages[:-1]):
            if hasattr(msg, "content") and not getattr(msg, "tool_calls", None):
                candidate = extract_text(msg.content)
                if candidate.strip() and len(candidate.strip()) > 50:
                    final_text = candidate
                    break

    return (
        final_text if final_text.strip() else "Analysis could not be completed.",
        loop_messages,
        mw.token_records,
    )
