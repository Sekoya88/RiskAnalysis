import asyncio
import os
import queue
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from loguru import logger

from src.main import run_analysis
from src.agents.nodes import set_log_queue
from src.infrastructure.observability.langfuse_tracer import get_langfuse_handler, shutdown_langfuse
import src.db as db

from evaluation.collector import RunTraceCollector
from evaluation.metrics import compute_metric_scores_with_report, retrieval_prf1
from evaluation.schemas import GroundTruth, GroundTruthRetrieval, GroundTruthTools

# ── WebSocket Manager for Live Logs ──────────────────────────────────
log_queue: queue.Queue = queue.Queue(maxsize=1000)
set_log_queue(log_queue)


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


async def log_broadcaster():
    """Background task: drain log_queue and broadcast to all WebSocket clients."""
    while True:
        try:
            msg = await asyncio.to_thread(log_queue.get, timeout=0.1)
            await manager.broadcast(msg)
            log_queue.task_done()
        except queue.Empty:
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Broadcaster error: {e}")
            await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    asyncio.create_task(log_broadcaster())
    logger.info("FastAPI Server Started - Log broadcaster running.")
    yield
    shutdown_langfuse()
    logger.info("Langfuse flushed — shutdown complete.")


app = FastAPI(
    title="RiskAnalysis Agentic API",
    description="API for the multi-agent Risk Assessment framework.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/runtime-info")
async def runtime_info():
    """Expose DB profile, PPO, Langfuse URL/reachability for the UI (no secrets)."""
    import httpx

    from src.rl.inference import (
        ppo_checkpoint_file_exists,
        ppo_disabled,
        ppo_policy_effective,
        resolved_ppo_checkpoint_path,
        torch_available,
    )

    lf_host = os.getenv("LANGFUSE_HOST", "http://localhost:3001").rstrip("/")
    lf_keys = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
    lf_reachable = False
    if lf_keys:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                r = await client.get(lf_host, follow_redirects=True)
                lf_reachable = r.status_code < 500
        except Exception:
            lf_reachable = False

    return {
        "api_version": app.version,
        "database_profile": "postgres" if os.getenv("DATABASE_URL") else "sqlite",
        "ppo_disabled": ppo_disabled(),
        "ppo_checkpoint_present": ppo_checkpoint_file_exists(),
        "ppo_torch_installed": torch_available(),
        "ppo_policy_configured": ppo_policy_effective(),
        "ppo_score_delta_default": float(os.getenv("PPO_SCORE_DELTA", "0.1")),
        "langfuse_host": lf_host,
        "langfuse_keys_configured": lf_keys,
        "langfuse_reachable": lf_reachable,
    }


# ── WebSocket ─────────────────────────────────────────────────────────

@app.websocket("/api/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    """Connect here to receive live agent execution logs."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ── REST Endpoints ───────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    query: str = Field(..., description="The risk analysis query.")
    use_redis: bool = Field(default=True, description="Use Redis for LangGraph state checkpointer.")
    model: str = Field(default="qwen3.5", description="Model to use.")
    # Optional labels for retrieval / faithfulness / tool-order metrics (UI « ground truth »)
    metrics_relevant_urls: list[str] | None = Field(
        default=None,
        description="News URLs judged relevant (P/R/F1 vs retrieved news).",
    )
    metrics_relevant_doc_keys: list[str] | None = Field(
        default=None,
        description="RAG source keys judged relevant (P/R/F1 vs RAG hits).",
    )
    metrics_reference_facts: list[str] | None = Field(
        default=None,
        description="Short strings expected in report text (faithfulness proxy).",
    )
    metrics_expected_tools: list[str] | None = Field(
        default=None,
        description="Expected tool call order prefix (tool-use accuracy).",
    )
    metrics_task_completed: bool | None = Field(
        default=None,
        description="If set, overrides heuristic task-completion score.",
    )


def metrics_labels_from_request(req: AnalyzeRequest) -> GroundTruth | None:
    urls = [u.strip() for u in (req.metrics_relevant_urls or []) if u and str(u).strip()]
    docs = [d.strip() for d in (req.metrics_relevant_doc_keys or []) if d and str(d).strip()]
    facts = [f.strip() for f in (req.metrics_reference_facts or []) if f and str(f).strip()]
    tools = [t.strip() for t in (req.metrics_expected_tools or []) if t and str(t).strip()]
    if not urls and not docs and not facts and not tools and req.metrics_task_completed is None:
        return None
    retrieval = None
    if urls or docs:
        retrieval = GroundTruthRetrieval(relevant_urls=set(urls), relevant_doc_keys=set(docs))
    tools_gt = GroundTruthTools(expected_tool_sequence=tools) if tools else None
    return GroundTruth(
        task_completed=req.metrics_task_completed,
        retrieval=retrieval,
        tools=tools_gt,
        reference_facts=facts,
    )


class FeedbackRequest(BaseModel):
    report_id: str
    url: str
    is_helpful: bool


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Run a full multi-agent risk analysis.
    Blocking — waits for the LangGraph pipeline to finish.
    For live updates connect to /api/ws/stream WebSocket.
    """
    os.environ["OLLAMA_MODEL"] = req.model
    thread_id = str(uuid.uuid4())

    # One Langfuse handler per request → clean trace isolation
    langfuse_handler = get_langfuse_handler(session_id=thread_id)

    await manager.broadcast({
        "type": "status",
        "message": f"Starting analysis for: {req.query}",
        "thread_id": thread_id,
    })
    start_time = time.time()

    trace_collector = RunTraceCollector(run_id=thread_id)
    try:
        report, sources, token_usage, structured_report = await run_analysis(
            query=req.query,
            use_redis=req.use_redis,
            thread_id=thread_id,
            langfuse_handler=langfuse_handler,
            trace_sink=trace_collector,
        )

        try:
            db.save_report(
                report_id=thread_id,
                entity=req.query[:50],
                scores={"overall": 0, "geopolitical": 0, "credit": 0, "market": 0, "esg": 0},
                report_text=report,
                sources=sources,
            )
        except Exception as e:
            logger.error(f"Failed to save report to DB: {e}")

        elapsed = time.time() - start_time
        await manager.broadcast({
            "type": "status",
            "message": f"Analysis complete in {elapsed:.1f}s",
            "thread_id": thread_id,
        })

        ended_at = datetime.utcnow()
        eval_record = trace_collector.build_run_record(
            query=req.query,
            success=True,
            error_message=None,
            token_usage=token_usage,
            sources=sources,
            structured_report=structured_report,
            final_report=report,
            ended_at=ended_at,
        )
        gt = metrics_labels_from_request(req)
        eval_scores = compute_metric_scores_with_report(
            eval_record,
            report,
            gt,
            model_hint=req.model,
        )
        run_metrics = eval_scores.model_dump()
        run_metrics["total_input_tokens"] = eval_record.total_input_tokens
        run_metrics["total_output_tokens"] = eval_record.total_output_tokens
        run_metrics["total_cached_tokens"] = eval_record.total_cached_tokens
        run_metrics["graph_node_names"] = eval_record.graph_node_names
        if gt and gt.retrieval and gt.retrieval.relevant_doc_keys:
            rp, rr, rf1 = retrieval_prf1(
                eval_record.retrieved_rag_keys,
                gt.retrieval.relevant_doc_keys,
            )
            if rp is not None:
                run_metrics["rag_retrieval_precision"] = rp
                run_metrics["rag_retrieval_recall"] = rr
                run_metrics["rag_retrieval_f1"] = rf1

        return {
            "status": "success",
            "thread_id": thread_id,
            "report": report,
            "sources": sources,
            "token_usage": token_usage,
            "structured_report": structured_report,
            "elapsed_seconds": round(elapsed, 2),
            "run_metrics": run_metrics,
        }
    except Exception as e:
        logger.exception("Analysis failed")
        await manager.broadcast({"type": "error", "message": str(e), "thread_id": thread_id})
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Submit RL feedback for a specific data source."""
    try:
        db.save_feedback(req.report_id, req.url, req.is_helpful)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to save feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to save feedback")


@app.get("/api/reports")
async def get_reports():
    """Retrieve history of generated reports."""
    return {"message": "Endpoint available for historical reports."}


if __name__ == "__main__":
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=True)
