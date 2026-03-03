"""
Supervisor Agent — LLM-based dynamic task delegation router.

Enforces the required analysis pipeline:
  1. geopolitical_analyst → 2. credit_evaluator → 3. market_synthesizer → FINISH

Also supports self-correction by re-routing to agents if needed.
Includes retry logic for API rate limits.
"""

import json
import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agents.prompts import SUPERVISOR_EVALUATION_PROMPT
from src.state.schema import AgentState
from src.utils import retry_with_backoff

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

    # ── All agents have reported → evaluate for self-correction ─────
    # Instead of passing the 50K+ raw execution message history, we pass
    # ONLY the clean, synthesized reports from `risk_signals`. This saves
    # massive amounts of tokens while preserving deep critical thinking.
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.0,
        max_output_tokens=512,
    )

    # Compile the reports for the supervisor to read
    reports_context = "\n\n".join(
        f"--- REPORT FROM: {signal.get('agent', 'UNKNOWN')} ---\n{signal.get('analysis', '')}"
        for signal in state.get("risk_signals", [])
    )

    system_msg = f"""{SUPERVISOR_EVALUATION_PROMPT}

Current iteration: {iteration_count}/10
Here are the final synthesized reports from your team:

{reports_context}
"""

    messages = [SystemMessage(content=system_msg)]

    print("   🧠 Supervisor evaluating completion based on final reports...")
    
    try:
        response = await retry_with_backoff(
            llm.ainvoke,
            messages,
            max_retries=3,
            base_delay=5.0,
        )
        content = _extract_text(response.content).strip()
    except Exception as e:
        print(f"   ⚠️ Supervisor evaluation failed ({e}). Defaulting to FINISH.")
        return {"next_agent": "FINISH"}

    # Parse the routing decision
    next_agent = "FINISH"
    try:
        if "{" in content:
            json_str = content[content.index("{"):content.rindex("}") + 1]
            decision = json.loads(json_str)
            candidate = decision.get("next", "FINISH")
            if candidate in AGENT_OPTIONS:
                next_agent = candidate
            print(f"   ➡️  Supervisor reasoning: {decision.get('reasoning', 'None')}")
    except (json.JSONDecodeError, ValueError):
        for option in AGENT_OPTIONS:
            if option.lower() in content.lower():
                next_agent = option
                break

    print(f"   ➡️  Supervisor decision: {next_agent}")
    return {"next_agent": next_agent}
