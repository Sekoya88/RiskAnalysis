"""
Domain Service — Report building utilities.

Pure logic for extracting and transforming LLM output.
"""

from __future__ import annotations

from typing import Any


def extract_text(content: Any) -> str:
    """Extract plain text from LLM structured content format."""
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


def strip_report_preamble(content: str) -> str:
    """Strip any LLM preamble before the structured report marker."""
    for marker in ("═══", "==="):
        if marker in content:
            idx = content.index(marker)
            return content[idx:]
    return content
