"""Orchestrates a traced run_analysis and produces SingleRunReport."""

from __future__ import annotations

import os
from datetime import datetime

from evaluation.collector import RunTraceCollector
from evaluation.metrics import compute_metric_scores_with_report
from evaluation.schemas import GroundTruth, RunRecord, SingleRunReport

# Lazy import avoids loading LangGraph at module import for pytest unit tests


async def evaluate_agent_run(
    query: str,
    *,
    trace_collector: RunTraceCollector | None = None,
    use_redis: bool = False,
    thread_id: str | None = None,
    ground_truth: GroundTruth | None = None,
    model_hint: str | None = None,
) -> SingleRunReport:
    """
    Run the full pipeline with tracing and return a JSON-ready report.

    Args:
        query: User query passed to run_analysis.
        trace_collector: If None, a new RunTraceCollector is created.
        model_hint: For cost estimate (e.g. os.environ OLLAMA_MODEL or gemini-2.5-flash).
    """
    from src.main import run_analysis

    collector = trace_collector or RunTraceCollector()
    mh = model_hint or os.getenv("OLLAMA_MODEL") or os.getenv("GOOGLE_GENAI_MODEL")

    err: str | None = None
    report_text = ""
    sources: dict = {}
    token_usage: list = []
    structured: dict | None = None
    success = True

    try:
        report_text, sources, token_usage, structured = await run_analysis(
            query=query,
            use_redis=use_redis,
            thread_id=thread_id,
            trace_sink=collector,
        )
    except Exception as e:
        success = False
        err = str(e)

    ended = datetime.utcnow()
    record = collector.build_run_record(
        query=query,
        success=success,
        error_message=err,
        token_usage=token_usage,
        sources=sources,
        structured_report=structured,
        final_report=report_text,
        ended_at=ended,
    )

    metrics = compute_metric_scores_with_report(
        record,
        report_text,
        ground_truth,
        model_hint=mh,
    )

    notes: list[str] = []
    if ground_truth and ground_truth.retrieval and ground_truth.retrieval.relevant_doc_keys:
        from evaluation.metrics import retrieval_prf1

        p, r, f1 = retrieval_prf1(
            record.retrieved_rag_keys,
            ground_truth.retrieval.relevant_doc_keys,
        )
        if p is not None:
            notes.append(f"RAG doc P/R/F1 (proxy): {p:.3f} / {r:.3f} / {f1:.3f}")

    return SingleRunReport(
        run_id=record.run_id,
        query=query,
        metrics=metrics,
        record=record,
        notes=notes,
    )


def run_record_from_synthetic_events(
    events: list[dict],
    *,
    run_id: str = "synthetic",
    query: str = "test",
    success: bool = True,
) -> RunRecord:
    """Build RunRecord from a list of events (for tests / demos without LLM)."""
    from datetime import datetime as _dt

    c = RunTraceCollector()
    c._run_id = run_id
    c._t0 = _dt.utcnow()
    for e in events:
        c(e)
    return c.build_run_record(
        query=query,
        success=success,
        error_message=None,
        token_usage=[{"agent": "demo", "input": 100, "output": 50, "cached": 0}],
        sources={"news": [{"url": "https://a.com/x", "title": "t"}], "rag": [], "market": []},
        structured_report=None,
        final_report="Demo report mentioning Apple Inc.",
    )
