"""
Agent Middleware — Cross-cutting concerns for the ReAct agent loop.

Follows the DeepAgents middleware pattern: each middleware intercepts
tool calls and LLM invocations to provide logging, token tracking,
and RL feedback without polluting agent node logic.

Usage:
    from src.agents.middleware import AgentMiddleware

    mw = AgentMiddleware(agent_name="geopolitical_analyst", log_queue=q)
    mw.on_iteration(1, 6)
    mw.on_tool_call("search_geopolitical_news")
    mw.on_llm_response(response)
    summary = mw.summary()
"""

from __future__ import annotations

import queue
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentMiddleware:
    """Middleware that captures logging, token usage, and tool call metrics."""

    agent_name: str
    log_queue: queue.Queue | None = None
    _token_records: list[dict] = field(default_factory=list)
    _tool_calls: list[str] = field(default_factory=list)

    # ── Logging ───────────────────────────────────────────────────────

    def emit(self, message: str) -> None:
        """Push a log message to the shared queue and stdout."""
        if self.log_queue is not None:
            try:
                self.log_queue.put_nowait(message)
            except queue.Full:
                pass
        print(f"   {message}")

    # ── Lifecycle hooks ───────────────────────────────────────────────

    def on_start(self, label: str | None = None) -> None:
        self.emit(f"{'🌍' if 'geo' in self.agent_name else '💳' if 'credit' in self.agent_name else '📊'} {label or self.agent_name} starting...")

    def on_iteration(self, iteration: int, max_iterations: int) -> None:
        self.emit(f"💭 Iteration {iteration}/{max_iterations} — thinking...")

    def on_tool_call(self, tool_name: str) -> None:
        self._tool_calls.append(tool_name)
        self.emit(f"🔧 Calling tool: {tool_name}")

    def on_llm_response(self, response: Any) -> dict:
        """Extract and record token usage from an LLM response."""
        usage = _extract_token_usage(response)
        self._token_records.append(usage)
        if usage["input_tokens"] > 0:
            self.emit(f"📊 Tokens: {usage['input_tokens']:,} in / {usage['output_tokens']:,} out")
        return usage

    def on_final_response(self) -> None:
        self.emit("✍️ Generating final response...")

    def on_done(self) -> None:
        s = self.summary()
        self.emit(f"✅ {self.agent_name} done — {s['input']:,} in / {s['output']:,} out")

    def on_structured_report(self, entity: str, score: int, rating: str) -> None:
        self.emit(f"📋 Structured: {entity} — {score}/100 [{rating}]")

    # ── Aggregation ───────────────────────────────────────────────────

    def summary(self) -> dict:
        """Return aggregated token usage and tool call stats."""
        total_in = sum(t["input_tokens"] for t in self._token_records)
        total_out = sum(t["output_tokens"] for t in self._token_records)
        total_cached = sum(t["cached_tokens"] for t in self._token_records)
        return {
            "agent": self.agent_name,
            "input": total_in,
            "output": total_out,
            "cached": total_cached,
            "tool_calls": list(self._tool_calls),
            "num_tool_calls": len(self._tool_calls),
            "num_llm_calls": len(self._token_records),
        }

    @property
    def token_records(self) -> list[dict]:
        return list(self._token_records)


def _extract_token_usage(response: Any) -> dict:
    """Extract token usage from an LLM response.

    LangChain ChatOllama exposes usage_metadata with input_tokens/output_tokens.
    """
    usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}
    try:
        um = getattr(response, "usage_metadata", None)
        if um:
            if isinstance(um, dict):
                usage["input_tokens"] = um.get("input_tokens", 0)
                usage["output_tokens"] = um.get("output_tokens", 0)
                usage["cached_tokens"] = um.get("cache_read_input_tokens", 0) or um.get("cached_tokens", 0)
            else:
                usage["input_tokens"] = getattr(um, "input_tokens", 0)
                usage["output_tokens"] = getattr(um, "output_tokens", 0)

        if usage["output_tokens"] == 0 and hasattr(response, "content") and response.content:
            usage["output_tokens"] = len(str(response.content)) // 4
    except Exception:
        pass
    return usage
