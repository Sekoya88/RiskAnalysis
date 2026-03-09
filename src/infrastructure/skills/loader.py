"""Infrastructure — Skill file loader (SKILL.md with YAML frontmatter)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml


@dataclass(frozen=True)
class Skill:
    """Parsed representation of a SKILL.md file."""

    name: str
    description: str
    instructions: str
    allowed_tools: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def prompt(self, **kwargs: str) -> str:
        text = self.instructions
        for key, value in kwargs.items():
            text = text.replace(f"{{{key}}}", value)
        return text


def _parse_skill_md(content: str) -> tuple[dict[str, Any], str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not match:
        return {}, content
    frontmatter = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()
    return frontmatter, body


@lru_cache(maxsize=16)
def load_skill(skill_name: str, skills_dir: str | None = None) -> Skill:
    """Load and parse a skill from the skills/ directory."""
    if skills_dir is None:
        skills_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "skills",
        )

    skill_path = os.path.join(skills_dir, skill_name, "SKILL.md")
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
    """Convenience: load a skill and return its prompt with substitutions."""
    skill = load_skill(skill_name)
    return skill.prompt(**kwargs)


def list_skills(skills_dir: str | None = None) -> list[Skill]:
    """List all available skills."""
    if skills_dir is None:
        skills_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "skills",
        )
    skills = []
    if not os.path.isdir(skills_dir):
        return skills
    for entry in sorted(os.listdir(skills_dir)):
        skill_md = os.path.join(skills_dir, entry, "SKILL.md")
        if os.path.isfile(skill_md):
            try:
                skills.append(load_skill(entry, skills_dir))
            except Exception:
                pass
    return skills
