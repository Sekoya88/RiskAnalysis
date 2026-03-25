#!/usr/bin/env python3
"""Simulated metrics run (no LLM). Run: python -m evaluation.examples.sim_full_run"""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.aggregate import aggregate_reports
from evaluation.evaluator import run_record_from_synthetic_events
from evaluation.metrics import compute_metric_scores_with_report
from evaluation.reporters import write_json_report
from evaluation.schemas import GroundTruth, GroundTruthRetrieval, GroundTruthTools, SingleRunReport


def main() -> None:
    events = [
        {"type": "run_start", "t_wall": 0.0},
        {"type": "graph_node", "node": "supervisor", "elapsed_s": 0.1},
        {"type": "graph_node", "node": "geopolitical_analyst", "elapsed_s": 2.0},
        {"type": "llm_message", "role": "assistant"},
        {"type": "tool_call", "tool": "search_geopolitical_news"},
        {"type": "tool_call", "tool": "search_web_general"},
        {"type": "graph_node", "node": "credit_agent", "elapsed_s": 5.0},
        {"type": "graph_node", "node": "market_synthesizer", "elapsed_s": 8.0},
        {"type": "graph_stream_end", "elapsed_s": 8.5},
        {"type": "run_end", "has_report": True, "news_sources": 2, "rag_sources": 1},
    ]

    record = run_record_from_synthetic_events(
        events,
        run_id="sim-001",
        query="Risk assessment for Apple Inc.",
        success=True,
    )

    gt = GroundTruth(
        task_completed=True,
        retrieval=GroundTruthRetrieval(
            relevant_urls={"https://a.com/x", "https://reuters.com/foo"},
        ),
        tools=GroundTruthTools(
            expected_tool_sequence=["search_geopolitical_news", "search_web_general"],
        ),
        reference_facts=["Apple Inc.", "risk"],
    )

    report_text = (
        "Integrated risk report for Apple Inc. covering geopolitical and credit risk. "
        "Key risk drivers include supply chain exposure."
    )

    metrics = compute_metric_scores_with_report(
        record,
        report_text,
        gt,
        model_hint="gemini-2.5-flash",
    )

    sr = SingleRunReport(
        run_id=record.run_id,
        query=record.query,
        metrics=metrics,
        record=record,
        notes=["Simulated — no model invoked."],
    )

    out_dir = Path(__file__).resolve().parents[2] / "output"
    write_json_report(sr, out_dir / "sim_metrics.json")
    agg = aggregate_reports([sr])
    write_json_report(agg, out_dir / "sim_aggregate.json")

    print(json.dumps(json.loads(sr.model_dump_json()), indent=2)[:2000])
    print(f"\nWrote: {out_dir / 'sim_metrics.json'}")


if __name__ == "__main__":
    main()
