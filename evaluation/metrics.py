"""Pure metric functions from RunRecord + optional GroundTruth."""

from __future__ import annotations

from typing import Any

from evaluation.schemas import GroundTruth, MetricScores, RunRecord

# USD per 1M tokens — rough defaults; override via pricing dict
_DEFAULT_PRICING = {
    "gemini-2.5-flash": {"in": 0.075, "out": 0.30},
    "gemini-2.0-flash": {"in": 0.075, "out": 0.30},
    "default_cloud": {"in": 0.30, "out": 2.50},
    "default_local": {"in": 0.0, "out": 0.0},
}


def _normalize_url(u: str) -> str:
    return u.strip().rstrip("/").lower()


def retrieval_prf1(
    retrieved: list[str],
    relevant: set[str],
) -> tuple[float | None, float | None, float | None]:
    if not relevant:
        return None, None, None
    rel_norm = {_normalize_url(x) for x in relevant}
    ret_norm = [_normalize_url(x) for x in retrieved if x]
    if not ret_norm:
        return 0.0, 0.0, 0.0
    hits = sum(1 for x in ret_norm if x in rel_norm)
    precision = hits / len(ret_norm)
    recall = hits / len(rel_norm) if rel_norm else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def faithfulness_from_facts(report_text: str, facts: list[str]) -> float | None:
    """Fraction of reference facts found as substrings in report (cheap proxy)."""
    if not facts:
        return None
    text = (report_text or "").lower()
    ok = sum(1 for f in facts if f.lower().strip() and f.lower() in text)
    return ok / len(facts)


def tool_sequence_accuracy(actual: list[str], expected: list[str]) -> float | None:
    if not expected:
        return None
    if not actual:
        return 0.0
    n = min(len(actual), len(expected))
    if n == 0:
        return 0.0
    matches = sum(1 for i in range(n) if actual[i] == expected[i])
    return matches / len(expected)


def estimate_cost_usd(
    record: RunRecord,
    model_hint: str | None,
    pricing: dict[str, Any] | None = None,
) -> float | None:
    table = {**_DEFAULT_PRICING, **(pricing or {})}
    key = (model_hint or "").lower()
    if "gemini" in key:
        p = table.get("gemini-2.5-flash", table["default_cloud"])
    elif key in ("qwen3.5", "lfm2", "llama3", "mistral", "") or "ollama" in key:
        p = table["default_local"]
    else:
        p = table["default_cloud"]

    cost_in = record.total_input_tokens * p["in"] / 1_000_000
    cost_out = record.total_output_tokens * p["out"] / 1_000_000
    return cost_in + cost_out


def robustness_score(recovery_events: int) -> float:
    """1.0 = no fallback; decays with each recovery."""
    if recovery_events <= 0:
        return 1.0
    return max(0.0, 1.0 - 0.2 * recovery_events)


def compute_metric_scores(
    record: RunRecord,
    ground_truth: GroundTruth | None = None,
    *,
    model_hint: str | None = None,
    pricing: dict[str, Any] | None = None,
) -> MetricScores:
    success = record.success
    success_component = 1.0 if success else 0.0

    task_done: float | None = None
    if ground_truth and ground_truth.task_completed is not None:
        task_done = 1.0 if ground_truth.task_completed else 0.0
    else:
        task_done = 1.0 if (success and record.has_final_report and record.graph_steps > 0) else 0.0
        if not success:
            task_done = 0.0

    p = r = f1 = None
    if ground_truth and ground_truth.retrieval and ground_truth.retrieval.relevant_urls:
        p, r, f1 = retrieval_prf1(
            record.retrieved_news_urls,
            ground_truth.retrieval.relevant_urls,
        )

    tool_acc = None
    if ground_truth and ground_truth.tools and ground_truth.tools.expected_tool_sequence:
        tool_acc = tool_sequence_accuracy(
            record.tool_names,
            ground_truth.tools.expected_tool_sequence,
        )

    cost = estimate_cost_usd(record, model_hint, pricing)

    return MetricScores(
        success=success,
        success_rate_component=success_component,
        task_completion_rate=task_done,
        retrieval_precision=p,
        retrieval_recall=r,
        retrieval_f1=f1,
        graph_step_count=record.graph_steps,
        latency_seconds=record.latency_seconds,
        llm_round_count=record.llm_message_count,
        tool_call_count=record.tool_call_count,
        estimated_cost_usd=cost,
        faithfulness_score=None,
        hallucination_rate_proxy=None,
        tool_use_accuracy=tool_acc,
        robustness_recovery_score=robustness_score(record.recovery_events),
    )


def compute_metric_scores_with_report(
    record: RunRecord,
    final_report: str,
    ground_truth: GroundTruth | None = None,
    *,
    model_hint: str | None = None,
    pricing: dict[str, Any] | None = None,
) -> MetricScores:
    base = compute_metric_scores(record, ground_truth, model_hint=model_hint, pricing=pricing)
    faith = None
    hall = None
    if ground_truth and ground_truth.reference_facts:
        faith = faithfulness_from_facts(final_report, ground_truth.reference_facts)
        if faith is not None:
            hall = max(0.0, min(1.0, 1.0 - faith))

    return base.model_copy(
        update={
            "faithfulness_score": faith,
            "hallucination_rate_proxy": hall,
        }
    )
