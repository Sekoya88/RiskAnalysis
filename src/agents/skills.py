"""
Skill Loader — Reads SKILL.md files following the Agent Skills specification.

Replaces the old prompts.py module. Skills use progressive disclosure:
each skill has YAML frontmatter (metadata) and markdown body (instructions).

Usage:
    from src.agents.skills import load_skill, get_skill_prompt

    skill = load_skill("geopolitical-analyst")
    prompt = get_skill_prompt("market-synthesizer", today="2026-03-07")
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

# ── Constants ─────────────────────────────────────────────────────────
SKILLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "skills",
)


@dataclass(frozen=True)
class Skill:
    """Parsed representation of a SKILL.md file."""

    name: str
    description: str
    instructions: str
    allowed_tools: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def prompt(self, **kwargs: str) -> str:
        """Return the instructions with optional placeholder substitution."""
        text = self.instructions
        for key, value in kwargs.items():
            text = text.replace(f"{{{key}}}", value)
        return text


def _parse_skill_md(content: str) -> tuple[dict[str, Any], str]:
    """Split a SKILL.md file into YAML frontmatter and markdown body."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not match:
        return {}, content

    frontmatter = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()
    return frontmatter, body


@lru_cache(maxsize=16)
def load_skill(skill_name: str) -> Skill:
    """Load and parse a skill from the skills/ directory.

    Args:
        skill_name: Directory name under skills/ (e.g., "geopolitical-analyst").

    Returns:
        A Skill dataclass with parsed metadata and instructions.

    Raises:
        FileNotFoundError: If the SKILL.md file doesn't exist.
    """
    skill_path = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
    if not os.path.isfile(skill_path):
        raise FileNotFoundError(f"Skill not found: {skill_path}")

    with open(skill_path, "r", encoding="utf-8") as f:
        content = f.read()

    frontmatter, body = _parse_skill_md(content)

    allowed_tools = frontmatter.get("allowed-tools", [])
    if isinstance(allowed_tools, str):
        allowed_tools = [allowed_tools]

    return Skill(
        name=frontmatter.get("name", skill_name),
        description=frontmatter.get("description", ""),
        instructions=body,
        allowed_tools=tuple(allowed_tools),
        metadata=frontmatter.get("metadata", {}),
    )


def get_skill_prompt(skill_name: str, **kwargs: str) -> str:
    """Convenience: load a skill and return its prompt with substitutions.

    Args:
        skill_name: Directory name under skills/.
        **kwargs: Placeholder values (e.g., today="2026-03-07").

    Returns:
        The skill instructions as a string, with placeholders replaced.
    """
    skill = load_skill(skill_name)
    return skill.prompt(**kwargs)


def list_skills() -> list[Skill]:
    """List all available skills in the skills/ directory."""
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills
    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_md = os.path.join(SKILLS_DIR, entry, "SKILL.md")
        if os.path.isfile(skill_md):
            try:
                skills.append(load_skill(entry))
            except Exception:
                pass
    return skills
