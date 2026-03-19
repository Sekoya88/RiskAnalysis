import asyncio
import os
import queue
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from loguru import logger

from src.main import run_analysis
from src.agents.nodes import set_log_queue
from src.infrastructure.observability.langfuse_tracer import get_langfuse_handler, shutdown_langfuse
import src.db as db

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

    try:
        report, sources, token_usage, structured_report = await run_analysis(
            query=req.query,
            use_redis=req.use_redis,
            thread_id=thread_id,
            langfuse_handler=langfuse_handler,
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

        return {
            "status": "success",
            "thread_id": thread_id,
            "report": report,
            "sources": sources,
            "token_usage": token_usage,
            "structured_report": structured_report,
            "elapsed_seconds": round(elapsed, 2),
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
