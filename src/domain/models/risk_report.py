"""
Domain Models — Risk Report value objects.

Pure Pydantic models with zero infrastructure dependency.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field


class Scenario(BaseModel):
    """A single risk scenario (bull/base/bear)."""

    label: str = Field(description="BULL / BASE / BEAR")
    probability_pct: int = Field(ge=0, le=100, description="Probability percentage")
    description: str = Field(description="Scenario description and impact")


class RiskReport(BaseModel):
    """Structured risk assessment report — the core domain aggregate."""

    entity: str = Field(default="Unknown", description="Company or entity name")
    date: str = Field(default="", description="Report date (YYYY-MM-DD)")
    overall_score: int = Field(default=0, ge=0, le=100)
    geopolitical_score: int = Field(default=0, ge=0, le=100)
    credit_score: int = Field(default=0, ge=0, le=100)
    market_score: int = Field(default=0, ge=0, le=100)
    esg_score: int = Field(default=0, ge=0, le=100)
    credit_rating: str = Field(default="N/A", description="Internal credit rating (AAA-D)")
    credit_outlook: str = Field(default="Stable", description="Positive / Stable / Negative")
    executive_summary: str = Field(default="")
    key_risk_factors: list[str] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)

    def to_scores_dict(self) -> dict:
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
    """Fallback parser: extract structured data from free-text report via regex."""

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

    risk_factors: list[str] = []
    factors_match = re.search(
        r"KEY RISK FACTORS.*?\n((?:\d+\..+\n?)+)", report_text, re.DOTALL
    )
    if factors_match:
        for line in factors_match.group(1).strip().split("\n"):
            cleaned = re.sub(r"^\d+\.\s*", "", line).strip()
            if cleaned:
                risk_factors.append(cleaned)

    scenarios: list[Scenario] = []
    for label in ["BULL", "BASE", "BEAR"]:
        m = re.search(
            rf"{label}\s+CASE\s*\((\d+)%\s*probability\):\s*(.+?)(?:\n|$)",
            report_text,
        )
        if m:
            scenarios.append(
                Scenario(label=label, probability_pct=int(m.group(1)), description=m.group(2).strip())
            )

    recommendations: list[str] = []
    rec_match = re.search(r"RECOMMENDATIONS.*?\n((?:\d+\..+\n?)+)", report_text, re.DOTALL)
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
