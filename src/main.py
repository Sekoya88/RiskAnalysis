"""
Main Entrypoint — Runs the multi-agent risk assessment framework.

Supports both:
  1. Redis-backed persistent state (production / Docker)
  2. In-memory state (local development / demo)

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
    print("\n" + "═" * 70)
    print("  🌐 AGENTIC RISK ASSESSMENT FRAMEWORK")
    print("  Multi-Agent LLM System for Credit & Geopolitical Risk")
    print("  Stack: LangGraph • Gemini 2.5 Flash • ChromaDB • Redis")
    print("═" * 70 + "\n")


async def run_analysis(
    query: str,
    use_redis: bool = False,
    thread_id: str | None = None,
) -> str:
    """Execute a full multi-agent risk analysis.

    Args:
        query: The risk assessment query / prompt.
        use_redis: If True, use Redis-backed state persistence.
        thread_id: Optional thread ID for state continuity.

    Returns:
        The final integrated risk report.
    """
    from src.graph import build_graph, build_graph_with_redis

    thread_id = thread_id or str(uuid.uuid4())

    # ── Build graph ───────────────────────────────────────────────────
    if use_redis:
        graph, checkpointer = await build_graph_with_redis()
    else:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        graph = build_graph(checkpointer=checkpointer)

    # ── Initial state ─────────────────────────────────────────────────
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "next_agent": "",
        "current_company": "",
        "risk_signals": [],
        "final_report": "",
        "iteration_count": 0,
    }

    config = {"configurable": {"thread_id": thread_id}}

    # ── Execute ───────────────────────────────────────────────────────
    print(f"📋 Query: {query[:100]}...")
    print(f"🔑 Thread ID: {thread_id}")
    print(f"💾 State Backend: {'Redis' if use_redis else 'In-Memory'}")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 70)

    start_time = time.time()
    final_state = None

    async for event in graph.astream(initial_state, config=config):
        for node_name, node_output in event.items():
            elapsed = time.time() - start_time
            print(f"\n⚡ [{elapsed:.1f}s] Node: {node_name}")

            if "messages" in node_output:
                for msg in node_output["messages"]:
                    if hasattr(msg, "name") and msg.name:
                        print(f"   Agent: {msg.name}")
                    content_preview = msg.content[:200] if msg.content else ""
                    print(f"   Output: {content_preview}...")

            if "next_agent" in node_output:
                print(f"   ➡️  Next: {node_output['next_agent']}")

            final_state = node_output

    elapsed = time.time() - start_time
    print("\n" + "═" * 70)
    print(f"✅ Analysis completed in {elapsed:.1f} seconds")
    print("═" * 70)

    # ── Extract final report + sources ────────────────────────────────
    from src.agents.nodes import _extract_text
    from langchain_core.messages import ToolMessage as _ToolMessage

    final_report = ""
    sources = {"news": [], "market": [], "rag": []}

    # Try to get the report from graph state snapshot
    try:
        snapshot = await graph.aget_state(config)
        if snapshot and snapshot.values:
            # First try the final_report field
            raw = snapshot.values.get("final_report", "")
            final_report = _extract_text(raw).strip()

            # Fallback: extract from market_synthesizer messages
            messages = snapshot.values.get("messages", [])
            if not final_report:
                for msg in reversed(messages):
                    if hasattr(msg, "name") and msg.name == "market_synthesizer":
                        final_report = _extract_text(msg.content).strip()
                        if final_report:
                            break

                # Last fallback: last named agent message
                if not final_report and messages:
                    for msg in reversed(messages):
                        if hasattr(msg, "name") and msg.name:
                            final_report = _extract_text(msg.content).strip()
                            if final_report:
                                break

            # ── Extract sources from ToolMessages ─────────────────────
            for msg in messages:
                if not isinstance(msg, _ToolMessage):
                    continue
                try:
                    data = json.loads(msg.content)
                except (json.JSONDecodeError, TypeError):
                    continue

                # News articles (from search_geopolitical_news)
                if "articles" in data:
                    for article in data["articles"]:
                        entry = {
                            "title": article.get("title", ""),
                            "url": article.get("url", ""),
                            "source": article.get("source", ""),
                            "date": article.get("date", ""),
                        }
                        if entry["title"] and entry not in sources["news"]:
                            sources["news"].append(entry)

                # Web search results (from search_web_general)
                elif "results" in data and "articles" not in data:
                    for result in data["results"]:
                        entry = {
                            "title": result.get("title", ""),
                            "url": result.get("href", ""),
                            "source": "Web",
                            "date": "",
                        }
                        if entry["title"] and entry not in sources["news"]:
                            sources["news"].append(entry)

                # Market data (from get_market_data)
                elif "market_snapshot" in data or "company" in data:
                    entry = {
                        "company": data.get("company", ""),
                        "ticker": data.get("ticker", ""),
                        "price": data.get("market_snapshot", {}).get("current_price", ""),
                        "pe_ratio": data.get("financial_ratios", {}).get("pe_ratio", ""),
                    }
                    if entry["company"] and entry not in sources["market"]:
                        sources["market"].append(entry)

                # RAG documents (from search_corporate_disclosures)
                elif "documents" in data:
                    for doc in data["documents"]:
                        entry = {
                            "source": doc.get("source", ""),
                            "company": doc.get("company", ""),
                            "type": doc.get("document_type", ""),
                            "score": doc.get("relevance_score", 0),
                        }
                        if entry["source"] and entry not in sources["rag"]:
                            sources["rag"].append(entry)

    except Exception as e:
        final_report = final_report or f"Report extraction failed: {e}"

    return final_report, sources


async def main():
    """Main entry point."""
    _print_banner()

    # Parse CLI args
    use_redis = "--redis" in sys.argv
    custom_query = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            custom_query = arg
            break

    query = custom_query or DEFAULT_QUERIES[0]

    print("🚀 Initializing agents...\n")

    report, sources = await run_analysis(query=query, use_redis=use_redis)

    print("\n" + "═" * 70)
    print("  📊 FINAL INTEGRATED RISK REPORT")
    print("═" * 70)
    print(report)
    print("\n" + "═" * 70)

    # Save report to file
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

    print(f"\n💾 Report saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
