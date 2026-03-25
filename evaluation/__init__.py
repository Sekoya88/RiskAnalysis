"""
Agentic workflow evaluation — traces, metrics, JSON reports.

Usage (non-breaking):
    from evaluation import RunTraceCollector, evaluate_agent_run, write_json_report
    from pathlib import Path

    report = await evaluate_agent_run(query="Assess AAPL risk", use_redis=False)
    write_json_report(report, Path("output/eval_last.json"))
"""

from evaluation.aggregate import aggregate_reports
from evaluation.collector import RunTraceCollector
from evaluation.evaluator import evaluate_agent_run
from evaluation.reporters import write_json_report
from evaluation.schemas import EvaluationReport, GroundTruth, GlobalAggregate

__all__ = [
    "RunTraceCollector",
    "evaluate_agent_run",
    "write_json_report",
    "aggregate_reports",
    "EvaluationReport",
    "GroundTruth",
    "GlobalAggregate",
]
