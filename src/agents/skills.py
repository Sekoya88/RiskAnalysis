"""
Backward-compatible shim — re-exports from new DDD locations.
"""

from src.infrastructure.skills.loader import Skill, load_skill, get_skill_prompt, list_skills

__all__ = ["Skill", "load_skill", "get_skill_prompt", "list_skills"]
