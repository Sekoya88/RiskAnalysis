"""
Backward-compatible shim — re-exports from new DDD locations.

app.py and other legacy code import from here.
"""

# Re-export domain models
from src.domain.models.risk_report import RiskReport, Scenario, parse_report_to_structured

# Re-export application DTO
from src.application.dto import AgentState

__all__ = ["RiskReport", "Scenario", "parse_report_to_structured", "AgentState"]
