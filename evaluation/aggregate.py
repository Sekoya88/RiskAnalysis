"""Aggregate multiple SingleRunReport into GlobalAggregate."""

from __future__ import annotations

from statistics import mean

from evaluation.schemas import GlobalAggregate, SingleRunReport


def aggregate_reports(reports: list[SingleRunReport]) -> GlobalAggregate:
    if not reports:
        return GlobalAggregate(
            n_runs=0,
            mean_success_rate=0.0,
            mean_latency_seconds=0.0,
            mean_tool_calls=0.0,
            mean_graph_steps=0.0,
            total_estimated_cost_usd=0.0,
            runs=[],
        )

    costs = [r.metrics.estimated_cost_usd for r in reports if r.metrics.estimated_cost_usd is not None]
    total_cost = sum(costs) if costs else None

    return GlobalAggregate(
        n_runs=len(reports),
        mean_success_rate=mean([r.metrics.success_rate_component for r in reports]),
        mean_latency_seconds=mean([r.metrics.latency_seconds for r in reports]),
        mean_tool_calls=mean([float(r.metrics.tool_call_count) for r in reports]),
        mean_graph_steps=mean([float(r.metrics.graph_step_count) for r in reports]),
        total_estimated_cost_usd=total_cost,
        runs=[r.run_id for r in reports],
    )
