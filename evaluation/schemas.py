"""Pydantic models for evaluation runs, ground truth, and aggregated reports."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    """Single raw event from trace_sink (flexible payload)."""

    model_config = {"extra": "allow"}

    type: str
    t_wall: float | None = None


class GroundTruthRetrieval(BaseModel):
    """URLs or doc ids judged relevant for a query — for precision/recall/F1."""

    relevant_urls: set[str] = Field(default_factory=set)
    relevant_doc_keys: set[str] = Field(default_factory=set)


class GroundTruthTools(BaseModel):
    """Expected tool names in order (prefix) for tool-use accuracy."""

    expected_tool_sequence: list[str] = Field(default_factory=list)


class GroundTruth(BaseModel):
    """Optional labels for an eval case."""

    task_completed: bool | None = None
    retrieval: GroundTruthRetrieval | None = None
    tools: GroundTruthTools | None = None
    reference_facts: list[str] = Field(default_factory=list)


class RunRecord(BaseModel):
    """Everything captured for one agent run (post-hoc)."""

    run_id: str
    query: str
    started_at: datetime
    ended_at: datetime
    success: bool
    error_message: str | None = None

    raw_events: list[dict[str, Any]] = Field(default_factory=list)

    graph_steps: int = 0
    graph_node_names: list[str] = Field(default_factory=list)
    recovery_events: int = 0

    llm_message_count: int = 0
    tool_call_count: int = 0
    tool_names: list[str] = Field(default_factory=list)

    latency_seconds: float = 0.0
    stream_elapsed_seconds: float | None = None

    token_usage: list[dict[str, Any]] = Field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_tokens: int = 0

    has_final_report: bool = False
    retrieved_news_urls: list[str] = Field(default_factory=list)
    retrieved_rag_keys: list[str] = Field(default_factory=list)

    structured_report_present: bool = False


class MetricScores(BaseModel):
    """Computed metrics (None = not applicable / not computed)."""

    success: bool
    success_rate_component: float = Field(ge=0.0, le=1.0)
    task_completion_rate: float | None = Field(default=None, ge=0.0, le=1.0)

    retrieval_precision: float | None = None
    retrieval_recall: float | None = None
    retrieval_f1: float | None = None

    graph_step_count: int = 0
    latency_seconds: float = 0.0
    llm_round_count: int = 0
    tool_call_count: int = 0

    estimated_cost_usd: float | None = None

    faithfulness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    hallucination_rate_proxy: float | None = Field(default=None, ge=0.0, le=1.0)

    tool_use_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)

    robustness_recovery_score: float | None = Field(default=None, ge=0.0, le=1.0)

    rl_human_feedback_note: str = (
        "Human votes on news URLs (Postgres) + recency (compute_rl_weight) → rerank / top-k. "
        "PPO loads data/ppo_source_policy.pt by default when present (override: PPO_SOURCE_POLICY_PATH; "
        "disable: PPO_DISABLED=1). PPO does not fine-tune the LLM."
    )


class SingleRunReport(BaseModel):
    """JSON-serializable report for one run."""

    schema_version: str = "1.0"
    run_id: str
    query: str
    metrics: MetricScores
    record: RunRecord
    notes: list[str] = Field(default_factory=list)


class GlobalAggregate(BaseModel):
    """Roll-up over multiple SingleRunReport objects."""

    n_runs: int
    mean_success_rate: float
    mean_latency_seconds: float
    mean_tool_calls: float
    mean_graph_steps: float
    total_estimated_cost_usd: float | None = None
    runs: list[str] = Field(default_factory=list)


# Backward alias for docs / user-facing name
EvaluationReport = SingleRunReport
