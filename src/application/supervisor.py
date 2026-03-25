"""Application — Supervisor agent (routing + self-correction)."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from src.application.dto import AgentState
from src.domain.services.report_builder import extract_text
from src.infrastructure.llm.factory import create_llm
from src.infrastructure.skills.loader import load_skill
from src.utils import retry_with_backoff

REQUIRED_PIPELINE = ["geopolitical_analyst", "credit_evaluator", "market_synthesizer"]
AGENT_OPTIONS = REQUIRED_PIPELINE + ["FINISH"]


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    """Supervisor — decides which specialist to invoke next."""
    iteration_count = state.get("iteration_count", 0)
    if iteration_count >= 10:
        logger.warning("Max iterations reached — finishing.")
        return {"next_agent": "FINISH"}

    agents_reported = [s.get("agent") for s in state.get("risk_signals", [])]

    # Deterministic routing: enforce pipeline order
    for agent in REQUIRED_PIPELINE:
        if agent not in agents_reported:
            logger.info(f"Supervisor: routing to {agent} (pipeline order)")
            return {"next_agent": agent}

    # All agents reported → evaluate for self-correction
    llm = create_llm(temperature=0.0, num_predict=512)

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

    messages = [
        SystemMessage(content=system_msg),
        HumanMessage(
            content=(
                "Evaluate the reports above. Reply with a single JSON object only, "
                'as described in the skill (e.g. {"next":"FINISH","reasoning":"..."}).'
            )
        ),
    ]

    logger.info("Supervisor evaluating completion based on final reports...")

    try:
        response = await retry_with_backoff(llm.ainvoke, messages, max_retries=3, base_delay=5.0)
        content = extract_text(response.content).strip()
    except Exception as e:
        logger.error(f"Supervisor evaluation failed ({e}). Defaulting to FINISH.")
        return {"next_agent": "FINISH"}

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
