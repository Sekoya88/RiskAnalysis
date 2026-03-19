"""
Custom LangChain callback that sends traces directly to Langfuse server v2
via /api/public/ingestion (bypasses the OTEL path used by SDK v3/v4).

Langfuse server v2.x does NOT support /api/public/otel/v1/traces.
Langfuse SDK v3/v4 sends via OTEL → incompatible with server v2.
This callback uses the old JSON ingestion endpoint directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from loguru import logger


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LangfuseV2Callback(BaseCallbackHandler):
    """
    Minimal Langfuse callback compatible with server v2.x.
    Sends LLM spans to /api/public/ingestion in batch.
    """

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        host: str = "http://localhost:3001",
        session_id: str | None = None,
    ):
        super().__init__()
        self.public_key = public_key
        self.secret_key = secret_key
        self.host = host.rstrip("/")
        self.session_id = session_id
        self._trace_id = str(uuid.uuid4())
        self._run_starts: Dict[str, dict] = {}
        self._client = httpx.Client(
            auth=(public_key, secret_key),
            timeout=5.0,
        )
        self._trace_created = False

    # ── Helpers ──────────────────────────────────────────────────────

    def _ingest(self, events: list[dict]) -> None:
        try:
            resp = self._client.post(
                f"{self.host}/api/public/ingestion",
                json={"batch": events},
            )
            if resp.status_code not in (200, 207):
                logger.warning(f"Langfuse ingestion returned {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Langfuse ingestion failed: {e}")

    def _ensure_trace(self, name: str = "risk-analysis") -> None:
        if self._trace_created:
            return
        self._trace_created = True
        self._ingest([{
            "id": self._trace_id + "-trace",
            "type": "trace-create",
            "timestamp": _now(),
            "body": {
                "id": self._trace_id,
                "name": name,
                "sessionId": self.session_id,
                "timestamp": _now(),
            },
        }])

    # ── LLM callbacks ────────────────────────────────────────────────

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._ensure_trace()
        run_id_str = str(run_id)
        model_name = (
            serialized.get("kwargs", {}).get("model")
            or serialized.get("id", ["unknown"])[-1]
        )
        self._run_starts[run_id_str] = {
            "start": _now(),
            "model": model_name,
            "prompts": prompts,
        }

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._ensure_trace()
        run_id_str = str(run_id)
        model_name = (
            serialized.get("kwargs", {}).get("model")
            or serialized.get("id", ["unknown"])[-1]
        )
        self._run_starts[run_id_str] = {
            "start": _now(),
            "model": model_name,
            "messages": [[m.dict() if hasattr(m, "dict") else str(m) for m in turn] for turn in messages],
        }

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        run_id_str = str(run_id)
        start_info = self._run_starts.pop(run_id_str, {})
        if not start_info:
            return

        output_text = ""
        if response.generations:
            gen = response.generations[0]
            if gen and hasattr(gen[0], "text"):
                output_text = gen[0].text[:2000]
            elif gen and hasattr(gen[0], "message"):
                output_text = str(getattr(gen[0].message, "content", ""))[:2000]

        # Extract token usage — Ollama, OpenAI, Gemini all store differently
        usage = {}
        if response.llm_output:
            lo = response.llm_output
            # OpenAI / Gemini format
            tu = lo.get("token_usage") or lo.get("usage_metadata") or {}
            # Ollama format: prompt_eval_count / eval_count
            prompt_tokens = (
                tu.get("prompt_tokens")
                or tu.get("input_tokens")
                or lo.get("prompt_eval_count", 0)
            )
            completion_tokens = (
                tu.get("completion_tokens")
                or tu.get("output_tokens")
                or lo.get("eval_count", 0)
            )
            if prompt_tokens or completion_tokens:
                usage = {
                    "input": prompt_tokens,
                    "output": completion_tokens,
                    "total": (prompt_tokens or 0) + (completion_tokens or 0),
                }

        # Fallback: check generation_info on the first generation
        if not usage and response.generations:
            gen = response.generations[0]
            if gen and hasattr(gen[0], "generation_info") and gen[0].generation_info:
                gi = gen[0].generation_info
                prompt_tokens = gi.get("prompt_eval_count", 0)
                completion_tokens = gi.get("eval_count", 0)
                if prompt_tokens or completion_tokens:
                    usage = {
                        "input": prompt_tokens,
                        "output": completion_tokens,
                        "total": prompt_tokens + completion_tokens,
                    }

        self._ingest([{
            "id": run_id_str,
            "type": "generation-create",
            "timestamp": start_info.get("start", _now()),
            "body": {
                "id": run_id_str,
                "traceId": self._trace_id,
                "name": start_info.get("model", "llm"),
                "model": start_info.get("model", "unknown"),
                "startTime": start_info.get("start", _now()),
                "endTime": _now(),
                "sessionId": self.session_id,
                "input": start_info.get("messages") or start_info.get("prompts"),
                "output": output_text,
                "usage": usage or None,
            },
        }])

    def on_llm_error(self, error: Exception, *, run_id: UUID, **kwargs: Any) -> None:
        run_id_str = str(run_id)
        self._run_starts.pop(run_id_str, None)

    def flush(self) -> None:
        """No-op: we send synchronously per event."""
        pass
