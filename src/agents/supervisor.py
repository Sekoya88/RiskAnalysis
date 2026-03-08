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
from langchain_ollama import ChatOllama
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None
from loguru import logger

from src.agents.skills import load_skill
from src.state.schema import AgentState
from src.utils import retry_with_backoff

load_dotenv()

# ── Required pipeline order ───────────────────────────────────────────
REQUIRED_PIPELINE = ["geopolitical_analyst", "credit_evaluator", "market_synthesizer"]
AGENT_OPTIONS = REQUIRED_PIPELINE + ["FINISH"]


def _extract_text(content: Any) -> str:
    """Extract plain text from LLM structured content."""
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
        logger.warning("Max iterations reached — finishing.")
        return {"next_agent": "FINISH"}

    # Determine which agents have already reported
    agents_reported = [s.get("agent") for s in state.get("risk_signals", [])]

    # ── Deterministic routing: enforce pipeline order ──────────────
    # If not all required agents have reported, route to the next one
    for agent in REQUIRED_PIPELINE:
        if agent not in agents_reported:
            logger.info(f"Supervisor: routing to {agent} (pipeline order)")
            return {"next_agent": agent}

    # ── All agents have reported → evaluate for self-correction ─────
    # Instead of passing the 50K+ raw execution message history, we pass
    # ONLY the clean, synthesized reports from `risk_signals`. This saves
    # massive amounts of tokens while preserving deep critical thinking.
    
    model = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
    
    if model.startswith("gemini"):
        if not ChatGoogleGenerativeAI:
            raise ImportError("langchain-google-genai is not installed.")
        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.0,
            max_output_tokens=512,
        )
    else:
        llm = ChatOllama(
            model=model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0.0,
            num_predict=512,
        )

    # Compile the reports for the supervisor to read
    reports_context = "\n\n".join(
        f"--- REPORT FROM: {signal.get('agent', 'UNKNOWN')} ---\n{signal.get('analysis', '')}"
        for signal in state.get("risk_signals", [])
    )

    supervisor_skill = load_skill("supervisor")
    evaluation_prompt = supervisor_skill.prompt()

    system_msg = f"""{evaluation_prompt}

Current iteration: {iteration_count}/10
Here are the final synthesized reports from your team:

{reports_context}
"""

    messages = [SystemMessage(content=system_msg)]

    logger.info("Supervisor evaluating completion based on final reports...")
    
    try:
        response = await retry_with_backoff(
            llm.ainvoke,
            messages,
            max_retries=3,
            base_delay=5.0,
        )
        content = _extract_text(response.content).strip()
    except Exception as e:
        logger.error(f"Supervisor evaluation failed ({e}). Defaulting to FINISH.")
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
            logger.debug(f"Supervisor reasoning: {decision.get('reasoning', 'None')}")
    except (json.JSONDecodeError, ValueError):
        for option in AGENT_OPTIONS:
            if option.lower() in content.lower():
                next_agent = option
                break

    logger.info(f"Supervisor decision: {next_agent}")
    return {"next_agent": next_agent}
