"""Collects trace_sink events into a list and builds RunRecord."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from evaluation.schemas import RunRecord


class RunTraceCollector:
    """
    Callable passed as trace_sink=collector to src.main.run_analysis.

    Keeps ordered raw events; evaluator turns them into RunRecord + metrics.
    """

    def __init__(self, run_id: str | None = None) -> None:
        self.events: list[dict[str, Any]] = []
        self._run_id = run_id or str(uuid.uuid4())
        self._t0: datetime | None = None

    @property
    def run_id(self) -> str:
        return self._run_id

    def __call__(self, event: dict[str, Any]) -> None:
        if self._t0 is None:
            self._t0 = datetime.utcnow()
        self.events.append(event)

    def build_run_record(
        self,
        *,
        query: str,
        success: bool,
        error_message: str | None,
        token_usage: list[dict[str, Any]],
        sources: dict[str, Any],
        structured_report: dict | None,
        final_report: str,
        ended_at: datetime | None = None,
    ) -> RunRecord:
        """Normalize collected events + pipeline outputs into RunRecord."""
        ended = ended_at or datetime.utcnow()
        started = self._t0 or ended

        graph_nodes: list[str] = []
        recoveries = 0
        llm_msgs = 0
        tools: list[str] = []
        stream_elapsed: float | None = None

        for ev in self.events:
            et = ev.get("type")
            if et == "graph_node":
                n = ev.get("node")
                if isinstance(n, str):
                    graph_nodes.append(n)
            elif et == "recovery":
                recoveries += 1
            elif et == "llm_message":
                llm_msgs += 1
            elif et == "tool_call":
                t = ev.get("tool")
                if isinstance(t, str):
                    tools.append(t)
            elif et == "graph_stream_end":
                se = ev.get("elapsed_s")
                if isinstance(se, (int, float)):
                    stream_elapsed = float(se)

        news_urls: list[str] = []
        for a in sources.get("news") or []:
            u = a.get("url") if isinstance(a, dict) else None
            if u:
                news_urls.append(str(u))

        rag_keys: list[str] = []
        for d in sources.get("rag") or []:
            if isinstance(d, dict):
                s = d.get("source")
                if s:
                    rag_keys.append(str(s))

        tin = sum(int(t.get("input", 0) or 0) for t in token_usage)
        tout = sum(int(t.get("output", 0) or 0) for t in token_usage)
        tcached = sum(int(t.get("cached", 0) or 0) for t in token_usage)

        latency = (ended - started).total_seconds()

        return RunRecord(
            run_id=self._run_id,
            query=query,
            started_at=started,
            ended_at=ended,
            success=success,
            error_message=error_message,
            raw_events=list(self.events),
            graph_steps=len(graph_nodes),
            graph_node_names=graph_nodes,
            recovery_events=recoveries,
            llm_message_count=llm_msgs,
            tool_call_count=len(tools),
            tool_names=tools,
            latency_seconds=latency,
            stream_elapsed_seconds=stream_elapsed,
            token_usage=token_usage,
            total_input_tokens=tin,
            total_output_tokens=tout,
            total_cached_tokens=tcached,
            has_final_report=bool(final_report and final_report.strip()),
            retrieved_news_urls=news_urls,
            retrieved_rag_keys=rag_keys,
            structured_report_present=structured_report is not None,
        )
