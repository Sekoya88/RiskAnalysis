"""Write SingleRunReport / GlobalAggregate to JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from evaluation.schemas import GlobalAggregate, SingleRunReport


def model_to_json_dict(model: BaseModel) -> dict[str, Any]:
    """Pydantic v2: mode json-compatible (datetimes → ISO)."""
    return json.loads(model.model_dump_json())


def write_json_report(model: BaseModel, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def load_json_report(path: Path) -> SingleRunReport:
    return SingleRunReport.model_validate_json(path.read_text(encoding="utf-8"))
