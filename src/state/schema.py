"""
Agent State Schema — Defines the typed state that flows through the
LangGraph multi-agent workflow.

Uses LangGraph's `Annotated` message reducer pattern for automatic
message accumulation across nodes.

Also defines the RiskReport structured output schema used by the
market_synthesizer to produce validated, parseable risk reports.
"""

from __future__ import annotations

import operator
import re
from typing import Annotated, Optional, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ── Structured Output: Risk Report ───────────────────────────────────

class Scenario(BaseModel):
    """A single risk scenario (bull/base/bear)."""
    label: str = Field(description="BULL / BASE / BEAR")
    probability_pct: int = Field(ge=0, le=100, description="Probability percentage")
    description: str = Field(description="Scenario description and impact")


class RiskReport(BaseModel):
    """Structured risk assessment report produced by the market synthesizer.

    This replaces free-text parsing with validated Pydantic fields.
    """
    entity: str = Field(default="Unknown", description="Company or entity name")
    date: str = Field(default="", description="Report date (YYYY-MM-DD)")
    overall_score: int = Field(default=0, ge=0, le=100, description="Overall risk score 0-100")
    geopolitical_score: int = Field(default=0, ge=0, le=100)
    credit_score: int = Field(default=0, ge=0, le=100)
    market_score: int = Field(default=0, ge=0, le=100)
    esg_score: int = Field(default=0, ge=0, le=100)
    credit_rating: str = Field(default="N/A", description="Internal credit rating (AAA-D)")
    credit_outlook: str = Field(default="Stable", description="Positive / Stable / Negative")
    executive_summary: str = Field(default="", description="2-3 paragraph synthesis")
    key_risk_factors: list[str] = Field(default_factory=list, description="Top risk factors")
    scenarios: list[Scenario] = Field(default_factory=list, description="Bull/Base/Bear scenarios")
    recommendations: list[str] = Field(default_factory=list, description="Actionable recommendations")
    sources: list[str] = Field(default_factory=list, description="Source citations")

    def to_scores_dict(self) -> dict:
        """Convert to the dict format expected by app.py and db.py."""
        return {
            "entity": self.entity,
            "overall": self.overall_score,
            "geopolitical": self.geopolitical_score,
            "credit": self.credit_score,
            "market": self.market_score,
            "esg": self.esg_score,
            "rating": f"{self.credit_rating} / {self.credit_outlook}",
        }


def parse_report_to_structured(report_text: str) -> RiskReport:
    """Fallback parser: extract structured data from free-text report via regex.

    Used when the LLM produces a text report instead of structured JSON.
    """
    def _extract_int(pattern: str, text: str, default: int = 0) -> int:
        m = re.search(pattern, text)
        return int(m.group(1)) if m else default

    def _extract_str(pattern: str, text: str, default: str = "") -> str:
        m = re.search(pattern, text)
        return m.group(1).strip() if m else default

    entity = _extract_str(r"ENTITY:\s*(.+)", report_text, "Unknown")
    date = _extract_str(r"DATE:\s*(\d{4}-\d{2}-\d{2})", report_text)

    overall = _extract_int(r"OVERALL RISK SCORE:\s*(\d+)/100", report_text)
    geo = _extract_int(r"Geopolitical Risk:\s*(\d+)/100", report_text)
    credit = _extract_int(r"Credit/Financial:\s*(\d+)/100", report_text)
    market = _extract_int(r"Market/Liquidity:\s*(\d+)/100", report_text)
    esg = _extract_int(r"ESG/Transition:\s*(\d+)/100", report_text)

    rating_str = _extract_str(r"INTERNAL CREDIT RATING:\s*(.+)", report_text, "N/A")
    parts = [p.strip() for p in rating_str.split("/")]
    credit_rating = parts[0] if parts else "N/A"
    credit_outlook = parts[1] if len(parts) > 1 else "Stable"

    # Extract key risk factors
    risk_factors = []
    factors_match = re.search(
        r"KEY RISK FACTORS.*?\n((?:\d+\..+\n?)+)",
        report_text, re.DOTALL,
    )
    if factors_match:
        for line in factors_match.group(1).strip().split("\n"):
            cleaned = re.sub(r"^\d+\.\s*", "", line).strip()
            if cleaned:
                risk_factors.append(cleaned)

    # Extract scenarios
    scenarios = []
    for label in ["BULL", "BASE", "BEAR"]:
        m = re.search(
            rf"{label}\s+CASE\s*\((\d+)%\s*probability\):\s*(.+?)(?:\n|$)",
            report_text,
        )
        if m:
            scenarios.append(Scenario(
                label=label,
                probability_pct=int(m.group(1)),
                description=m.group(2).strip(),
            ))

    # Extract recommendations
    recommendations = []
    rec_match = re.search(
        r"RECOMMENDATIONS.*?\n((?:\d+\..+\n?)+)",
        report_text, re.DOTALL,
    )
    if rec_match:
        for line in rec_match.group(1).strip().split("\n"):
            cleaned = re.sub(r"^\d+\.\s*", "", line).strip()
            if cleaned:
                recommendations.append(cleaned)

    return RiskReport(
        entity=entity,
        date=date,
        overall_score=overall,
        geopolitical_score=geo,
        credit_score=credit,
        market_score=market,
        esg_score=esg,
        credit_rating=credit_rating,
        credit_outlook=credit_outlook,
        key_risk_factors=risk_factors,
        scenarios=scenarios,
        recommendations=recommendations,
    )


# ── LangGraph Agent State ────────────────────────────────────────────

class AgentState(TypedDict):
    """Global state shared across all agent nodes in the LangGraph.

    Attributes:
        messages: Accumulated conversation messages (auto-merged via add_messages).
        next_agent: The next agent to route to, set by the supervisor.
        current_company: The company / entity currently being analyzed.
        risk_signals: Intermediate risk signals collected by individual agents.
        final_report: The synthesized final risk assessment report (raw text).
        structured_report: Validated RiskReport dict (structured output).
        iteration_count: Guard counter to prevent infinite loops.
        token_usage: Accumulated token counts per agent call.
    """

    # ── Core message stream (auto-accumulating) ──────────────────────
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # ── Routing ──────────────────────────────────────────────────────
    next_agent: str

    # ── Analysis context ─────────────────────────────────────────────
    current_company: str
    risk_signals: Annotated[list[dict], operator.add]

    # ── Output ───────────────────────────────────────────────────────
    final_report: str
    structured_report: Optional[dict]

    # ── Safety guard ─────────────────────────────────────────────────
    iteration_count: int

    # ── Token tracking ───────────────────────────────────────────────
    token_usage: Annotated[list[dict], operator.add]
