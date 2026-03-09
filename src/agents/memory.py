"""
Backward-compatible shim — re-exports from new DDD locations.
"""

import os
from src.infrastructure.persistence.memory import FileMemoryAdapter

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_MEMORY_PATH = os.path.join(_PROJECT_ROOT, "data", "AGENTS.md")

_adapter = FileMemoryAdapter(_MEMORY_PATH)


def load_memory() -> str:
    return _adapter.load()


def update_memory(entity: str, scores: dict, date: str | None = None) -> None:
    _adapter.update(entity, scores, date)
