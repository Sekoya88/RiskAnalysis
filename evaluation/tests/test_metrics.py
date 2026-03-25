"""Unit tests for metric helpers (no LangGraph)."""

from __future__ import annotations

import pytest

from evaluation.metrics import (
    estimate_cost_usd,
    retrieval_prf1,
    robustness_score,
    tool_sequence_accuracy,
)
from evaluation.schemas import RunRecord
from datetime import datetime


def test_retrieval_prf1_perfect() -> None:
    p, r, f1 = retrieval_prf1(
        ["https://A.COM/foo", "https://b.com/"],
        {"https://a.com/foo"},
    )
    assert p == pytest.approx(0.5)
    assert r == pytest.approx(1.0)
    assert f1 == pytest.approx(2 * 0.5 * 1.0 / 1.5)


def test_retrieval_empty_relevant() -> None:
    assert retrieval_prf1(["x"], set()) == (None, None, None)


def test_tool_sequence() -> None:
    assert tool_sequence_accuracy(
        ["a", "b", "c"],
        ["a", "b", "c"],
    ) == pytest.approx(1.0)
    assert tool_sequence_accuracy(["a", "x"], ["a", "b"]) == pytest.approx(0.5)


def test_robustness() -> None:
    assert robustness_score(0) == 1.0
    assert robustness_score(1) == pytest.approx(0.8)


def test_cost_local() -> None:
    rec = RunRecord(
        run_id="1",
        query="q",
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
        success=True,
        total_input_tokens=1_000_000,
        total_output_tokens=500_000,
    )
    c = estimate_cost_usd(rec, "qwen3.5")
    assert c == 0.0


def test_cost_gemini() -> None:
    rec = RunRecord(
        run_id="1",
        query="q",
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
        success=True,
        total_input_tokens=1_000_000,
        total_output_tokens=1_000_000,
    )
    c = estimate_cost_usd(rec, "gemini-2.5-flash")
    assert c is not None and c > 0
