"""Infrastructure — File-based agent memory (data/agent_memory.md)."""

from __future__ import annotations

import os
from datetime import datetime


MAX_RECENT_ANALYSES = 10


class FileMemoryAdapter:
    """MemoryPort implementation backed by a Markdown file."""

    def __init__(self, memory_path: str):
        self._path = memory_path

    def load(self) -> str:
        if not os.path.isfile(self._path):
            return ""
        with open(self._path, "r", encoding="utf-8") as f:
            return f.read()

    def update(self, entity: str, scores: dict, date: str | None = None) -> None:
        date = date or datetime.now().strftime("%Y-%m-%d")
        overall = scores.get("overall", scores.get("overall_score", 0))
        geo = scores.get("geopolitical", scores.get("geopolitical_score", 0))
        credit = scores.get("credit", scores.get("credit_score", 0))
        market = scores.get("market", scores.get("market_score", 0))
        esg = scores.get("esg", scores.get("esg_score", 0))
        rating = scores.get("rating", scores.get("credit_rating", "N/A"))

        entry = f"- **{entity}** ({date}): Overall={overall}/100 | Geo={geo} | Credit={credit} | Market={market} | ESG={esg} | Rating: {rating}"

        content = self.load()

        marker = "<!-- AUTO-UPDATED: Do not edit below this line manually -->"
        if marker in content:
            before, after = content.split(marker, 1)
            lines = [line for line in after.strip().split("\n") if line.startswith("- **")]
            lines.insert(0, entry)
            lines = lines[:MAX_RECENT_ANALYSES]
            content = f"{before}{marker}\n" + "\n".join(lines) + "\n"
        else:
            content += f"\n{marker}\n{entry}\n"

        entity_marker = "<!-- Entities analyzed previously with key findings -->"
        if entity_marker in content and entity.upper() not in content.upper():
            content = content.replace(
                entity_marker,
                f"{entity_marker}\n- **{entity}**: Last analyzed {date}, score {overall}/100",
            )

        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            f.write(content)
