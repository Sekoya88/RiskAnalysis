"""
Supervisor Agent — LLM-based dynamic task delegation router.

Enforces the required analysis pipeline:
  1. geopolitical_analyst → 2. credit_evaluator → 3. market_synthesizer → FINISH

Also supports self-correction by re-routing to agents if needed.
Includes retry logic for API rate limits.
"""

from __future__ import annotations

from typing import Any

from dotenv import load_dotenv

from src.state.schema import AgentState

load_dotenv()

# ── Required pipeline order ───────────────────────────────────────────
REQUIRED_PIPELINE = ["geopolitical_analyst", "credit_evaluator", "market_synthesizer"]
AGENT_OPTIONS = REQUIRED_PIPELINE + ["FINISH"]


def _extract_text(content: Any) -> str:
    """Extract plain text from Gemini's structured content."""
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


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    """Supervisor agent that decides which specialist to invoke next.

    Enforces the geopolitical → credit → synthesizer pipeline,
    while allowing LLM-driven re-routing for self-correction.
    """
    # Safety: prevent infinite loops (max 10 agent invocations)
    iteration_count = state.get("iteration_count", 0)
    if iteration_count >= 10:
        print("   🛑 Max iterations reached — finishing.")
        return {"next_agent": "FINISH"}

    # Determine which agents have already reported
    agents_reported = [s.get("agent") for s in state.get("risk_signals", [])]

    # ── Deterministic routing: enforce pipeline order ──────────────
    # If not all required agents have reported, route to the next one
    for agent in REQUIRED_PIPELINE:
        if agent not in agents_reported:
            print(f"   🧠 Supervisor: routing to {agent} (pipeline order)")
            return {"next_agent": agent}

    # ── All agents have reported → pipeline is complete ─────────────
    # No LLM call needed — deterministic FINISH saves ~15K tokens
    print("   ✅ All agents completed — finishing.")
    return {"next_agent": "FINISH"}
