"""
Main Entrypoint — Runs the multi-agent risk assessment framework.

Uses the DDD clean architecture:
  - Domain: models, ports, services (zero external deps)
  - Infrastructure: adapters (Ollama, ChromaDB, SQLite, etc.)
  - Application: agents, supervisor, graph (orchestration)
  - Container: dependency injection wiring

Usage:
    python -m src.main                          # Default demo query
    python -m src.main "Assess risk for TSLA"   # Custom query
    python -m src.main --redis                  # Force Redis backend
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from loguru import logger

load_dotenv()


# ── Default analysis queries ──────────────────────────────────────────
DEFAULT_QUERIES = [
    (
        "Perform a comprehensive credit and geopolitical risk assessment for "
        "Apple Inc. (AAPL), considering its supply chain exposure to China and "
        "Taiwan, the current US-China semiconductor tensions, and its financial "
        "health. Provide an integrated risk report with quantified risk scores."
    ),
]


def _print_banner():
    """Print startup banner."""
    logger.info("=" * 70)
    logger.info("  AGENTIC RISK ASSESSMENT FRAMEWORK")
    logger.info("  Multi-Agent LLM System for Credit & Geopolitical Risk")
    logger.info("  Stack: LangGraph | Ollama | ChromaDB (embeddinggemma) | Redis")
    logger.info("=" * 70)


async def run_analysis(
    query: str,
    use_redis: bool = False,
    thread_id: str | None = None,
) -> tuple[str, dict, list, dict | None]:
    """Execute a full multi-agent risk analysis."""
    from src.container import bootstrap
    from src.application.graph import build_graph

    # Bootstrap DI container (idempotent)
    bootstrap()

    thread_id = thread_id or str(uuid.uuid4())

    initial_state = {
        "messages": [HumanMessage(content=query)],
        "next_agent": "",
        "current_company": "",
        "risk_signals": [],
        "final_report": "",
        "structured_report": None,
        "iteration_count": 0,
        "token_usage": [],
    }
    config = {"configurable": {"thread_id": thread_id}}

    redis_cm = None

    if use_redis:
        try:
            from src.infrastructure.persistence.redis import get_redis_checkpointer
            redis_cm = get_redis_checkpointer()
        except ImportError:
            logger.warning("langgraph-checkpoint-redis not installed. Using in-memory state.")
        except Exception as e:
            err_msg = str(e)
            if "FT._LIST" in err_msg or "unknown command" in err_msg.lower():
                logger.warning(
                    "Redis missing RedisSearch module. Falling back to in-memory state."
                )
            else:
                logger.warning(f"Redis connection failed ({e}). Falling back to in-memory state.")

    if use_redis and redis_cm is not None:
        try:
            async with redis_cm as checkpointer:
                graph = build_graph(checkpointer=checkpointer)
                logger.info(f"Query: {query[:100]}...")
                logger.info(f"Thread ID: {thread_id}")
                logger.info("State Backend: Redis")
                return await _execute_graph(graph, initial_state, config)
        except Exception as e:
            logger.warning(f"Redis failed ({e}). Falling back to in-memory state.")

    # In-memory fallback
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)
    backend_label = "In-Memory (Redis failed)" if use_redis else "In-Memory"
    logger.info(f"Query: {query[:100]}...")
    logger.info(f"Thread ID: {thread_id}")
    logger.info(f"State Backend: {backend_label}")
    return await _execute_graph(graph, initial_state, config)


async def _execute_graph(graph, initial_state, config):
    """Run the graph and extract report + sources."""
    from src.domain.services.report_builder import extract_text
    from langchain_core.messages import ToolMessage as _ToolMessage

    start_time = time.time()

    async for event in graph.astream(initial_state, config=config):
        for node_name, node_output in event.items():
            elapsed = time.time() - start_time
            logger.info(f"[{elapsed:.1f}s] Node: {node_name}")

            if "messages" in node_output:
                for msg in node_output["messages"]:
                    if hasattr(msg, "name") and msg.name:
                        logger.debug(f"Agent: {msg.name}")
                    content_preview = msg.content[:200] if msg.content else ""
                    logger.debug(f"Output: {content_preview}...")

            if "next_agent" in node_output:
                logger.info(f"Next: {node_output['next_agent']}")

    elapsed = time.time() - start_time
    logger.info("=" * 70)
    logger.info(f"Analysis completed in {elapsed:.1f} seconds")
    logger.info("=" * 70)

    final_report = ""
    sources: dict = {"news": [], "market": [], "rag": []}
    token_usage = []
    structured_report = None

    try:
        from src.domain.services.risk_scoring import compute_rl_weight
        from src.db import get_source_feedback_score
        
        snapshot = await graph.aget_state(config)
        if snapshot and snapshot.values:
            raw = snapshot.values.get("final_report", "")
            final_report = extract_text(raw).strip()

            messages = snapshot.values.get("messages", [])
            if not final_report:
                for msg in reversed(messages):
                    if hasattr(msg, "name") and msg.name == "market_synthesizer":
                        final_report = extract_text(msg.content).strip()
                        if final_report:
                            break

                if not final_report and messages:
                    for msg in reversed(messages):
                        if hasattr(msg, "name") and msg.name:
                            final_report = extract_text(msg.content).strip()
                            if final_report:
                                break

            for msg in messages:
                if not isinstance(msg, _ToolMessage):
                    continue
                try:
                    data = json.loads(msg.content)
                except (json.JSONDecodeError, TypeError):
                    continue

                if "articles" in data:
                    for article in data["articles"]:
                        entry = {
                            "title": article.get("title", ""),
                            "url": article.get("url", ""),
                            "source": article.get("source", ""),
                            "date": article.get("date", ""),
                        }
                        if entry["title"] and entry not in sources["news"]:
                            # Compute RL Score
                            try:
                                base_score = get_source_feedback_score(entry["url"])
                                rl_weight = compute_rl_weight(base_score, entry["date"])
                                entry["score"] = rl_weight
                            except Exception:
                                pass
                            sources["news"].append(entry)

                elif "results" in data and "articles" not in data:
                    for result in data["results"]:
                        date_val = result.get("published_date", "")
                        if not date_val:
                            date_val = result.get("date", "")
                        entry = {
                            "title": result.get("title", ""),
                            "url": result.get("href", ""),
                            "source": "Web",
                            "date": date_val,
                        }
                        if entry["title"] and entry not in sources["news"]:
                            try:
                                base_score = get_source_feedback_score(entry["url"])
                                rl_weight = compute_rl_weight(base_score, entry["date"])
                                entry["score"] = rl_weight
                            except Exception:
                                pass
                            sources["news"].append(entry)

                elif "market_snapshot" in data or "company" in data:
                    entry = {
                        "company": data.get("company", ""),
                        "ticker": data.get("ticker", ""),
                        "price": data.get("market_snapshot", {}).get("current_price", ""),
                        "pe_ratio": data.get("financial_ratios", {}).get("pe_ratio", ""),
                    }
                    if entry["company"] and entry not in sources["market"]:
                        sources["market"].append(entry)

                elif "documents" in data:
                    for doc in data["documents"]:
                        entry = {
                            "source": doc.get("source", ""),
                            "company": doc.get("company", ""),
                            "type": doc.get("document_type", ""),
                            "score": doc.get("relevance_score", 0),
                            "content": doc.get("content", ""),
                        }
                        if entry["source"] and entry not in sources["rag"]:
                            sources["rag"].append(entry)

            # Sort by score descending and limit to 10
            if sources["news"]:
                sources["news"].sort(key=lambda x: x.get("score", 0), reverse=True)
                sources["news"] = sources["news"][:10]
                
            if sources["rag"]:
                sources["rag"].sort(key=lambda x: x.get("score", 0), reverse=True)
                sources["rag"] = sources["rag"][:10]

            token_usage = snapshot.values.get("token_usage", [])
            structured_report = snapshot.values.get("structured_report")

    except Exception as e:
        final_report = final_report or f"Report extraction failed: {e}"

    if not structured_report and final_report:
        from src.domain.models.risk_report import parse_report_to_structured
        structured_report = parse_report_to_structured(final_report).model_dump()

    return final_report, sources, token_usage, structured_report


async def main():
    """Main entry point."""
    _print_banner()

    use_redis = "--redis" in sys.argv
    custom_query = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            custom_query = arg
            break

    query = custom_query or DEFAULT_QUERIES[0]

    logger.info("Initializing agents...")
    report, sources, token_usage, structured_report = await run_analysis(query=query, use_redis=use_redis)

    logger.info("=" * 70)
    logger.info("  FINAL INTEGRATED RISK REPORT")
    logger.info("=" * 70)
    logger.info(report)
    logger.info("=" * 70)

    if token_usage:
        total_in = sum(t.get("input", 0) for t in token_usage)
        total_out = sum(t.get("output", 0) for t in token_usage)
        total_cached = sum(t.get("cached", 0) for t in token_usage)
        cost_in = total_in * 0.30 / 1_000_000
        cost_out = total_out * 2.50 / 1_000_000
        saved = total_cached * 0.27 / 1_000_000
        logger.info("  TOKEN USAGE")
        for t in token_usage:
            logger.info(f"     {t['agent']:25s} | {t['input']:,} in | {t['output']:,} out | {t.get('cached', 0):,} cached")
        logger.info(f"     {'TOTAL':25s} | {total_in:,} in | {total_out:,} out | {total_cached:,} cached")
        logger.info(f"  ESTIMATED COST: ${cost_in + cost_out:.4f} (saved ${saved:.4f} via caching)")
        logger.info("=" * 70)

    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"risk_report_{timestamp}.md")
    with open(output_path, "w") as f:
        f.write(f"# Risk Assessment Report\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Query**: {query}\n\n")
        f.write("---\n\n")
        f.write(report)
        f.write("\n\n---\n")
        f.write("<!-- INTERNAL_METADATA_START\n")
        f.write(json.dumps({"sources": sources}, indent=2))
        f.write("\nINTERNAL_METADATA_END -->\n")

    logger.info(f"Report saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
