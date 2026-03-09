"""
Agent Memory — Persistent context across sessions via AGENTS.md.

Follows the DeepAgents memory pattern: AGENTS.md provides always-present
context injected at startup, while skills handle on-demand capabilities.

The memory file stores:
  - Recent analysis summaries (entity, scores, date)
  - User preferences
  - Known entity context for comparison
"""

from __future__ import annotations

import os
from datetime import datetime

MEMORY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "AGENTS.md",
)

MAX_RECENT_ANALYSES = 10


def load_memory() -> str:
    """Load the AGENTS.md memory file content.

    Returns empty string if the file doesn't exist.
    """
    if not os.path.isfile(MEMORY_PATH):
        return ""
    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
        return f.read()


def update_memory(entity: str, scores: dict, date: str | None = None) -> None:
    """Append a new analysis entry to the memory file.

    Args:
        entity: Company/entity name.
        scores: Dict with overall, geopolitical, credit, market, esg scores.
        date: ISO date string (defaults to today).
    """
    date = date or datetime.now().strftime("%Y-%m-%d")
    overall = scores.get("overall", scores.get("overall_score", 0))
    geo = scores.get("geopolitical", scores.get("geopolitical_score", 0))
    credit = scores.get("credit", scores.get("credit_score", 0))
    market = scores.get("market", scores.get("market_score", 0))
    esg = scores.get("esg", scores.get("esg_score", 0))
    rating = scores.get("rating", scores.get("credit_rating", "N/A"))

    entry = f"- **{entity}** ({date}): Overall={overall}/100 | Geo={geo} | Credit={credit} | Market={market} | ESG={esg} | Rating: {rating}"

    content = load_memory()

    marker = "<!-- AUTO-UPDATED: Do not edit below this line manually -->"
    if marker in content:
        before, after = content.split(marker, 1)
        # Parse existing entries
        lines = [l for l in after.strip().split("\n") if l.startswith("- **")]
        lines.insert(0, entry)
        lines = lines[:MAX_RECENT_ANALYSES]
        content = f"{before}{marker}\n" + "\n".join(lines) + "\n"
    else:
        content += f"\n{marker}\n{entry}\n"

    # Update known entity context
    entity_marker = "<!-- Entities analyzed previously with key findings -->"
    if entity_marker in content and entity.upper() not in content.upper():
        content = content.replace(
            entity_marker,
            f"{entity_marker}\n- **{entity}**: Last analyzed {date}, score {overall}/100",
        )

    os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        f.write(content)
