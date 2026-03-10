# Agentic Risk Assessment Framework

Evaluate geopolitical, credit, and market risks using an AI multi-agent system.

[![Build Status](https://github.com/user/repo/workflows/build/badge.svg)](https://github.com/user/repo/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)

## Overview

This project is an advanced multi-agent risk assessment pipeline built with **LangGraph**. It replaces traditional scripts with specialized AI agents capable of reasoning, researching, and synthesizing financial risk reports.

You can run this framework entirely locally using **Ollama** or switch instantly to Google's **Gemini 2.5 Flash** via API for faster, production-grade reasoning.

## Local vs API Models

The framework supports seamless switching between local open-weights and cloud APIs.
You can select your preferred model directly from the Streamlit UI sidebar:

- **Local Models (Ollama)**
  - `qwen3.5` (9B parameters - Fast and excellent at tool use)
  - `lfm2` (24B parameters - Strong reasoning and synthesis)
  - *No API key required. Runs 100% locally and privately.*
- **Cloud Models (Google API)**
  - `gemini-2.5-flash` (Google GenAI)
  - *Requires a `GOOGLE_API_KEY` in your `.env` file or pasted directly into the UI.*

If you use Gemini, the application dynamically switches its backend LangChain driver to `langchain-google-genai` instead of `langchain-ollama`.

## Architecture (Clean DDD)

The codebase follows a **Domain-Driven Design** with clear separation of concerns:

```text
src/
├── domain/                 # Pure business logic, zero external deps
│   ├── models/             # RiskReport, Scenario, Source (value objects)
│   ├── ports/              # Protocol interfaces (LLM, Embedding, VectorStore, etc.)
│   └── services/           # RL scoring, report parsing
│
├── application/            # Orchestration layer
│   ├── agents/             # Geopolitical, Credit, Synthesizer (ReAct loop)
│   ├── supervisor.py       # Pipeline routing + self-correction
│   ├── graph.py            # LangGraph StateGraph builder
│   └── dto.py              # AgentState TypedDict
│
├── infrastructure/         # Concrete adapter implementations
│   ├── llm/                # OllamaLLMAdapter, GeminiLLMAdapter, factory
│   ├── embeddings/         # OllamaEmbeddingAdapter (embeddinggemma), HuggingFace fallback
│   ├── vector_store/       # PgVectorStoreAdapter, ChromaDB fallback
│   ├── retrieval/          # HybridRetriever (RRF fusion)
│   ├── data_sources/       # YahooFinanceAdapter, DuckDuckGoAdapter
│   ├── persistence/        # PostgreSQL / SQLite (reports + RL feedback), Redis, file memory
│   ├── skills/             # SKILL.md loader (YAML frontmatter + Markdown)
│   └── config/             # TOML config loader (deepagents.toml)
│
├── container.py            # Dependency injection (composition root)
└── main.py                 # CLI entrypoint
```

Every infrastructure component is hidden behind a **Port** (Python Protocol). Swapping Ollama for OpenAI, or PostgreSQL for another database, requires only a new adapter — no domain or application code changes.

## Multi-Agent Flow

The system runs a LangGraph state machine directed by a **Supervisor Agent**.

1. **Deterministic Routing:** The Supervisor first enforces a strict pipeline.
   - **Geopolitical Analyst** runs first to search global news and assess macro risks.
   - **Credit Risk Evaluator** runs second to fetch market data and assess financial health.
   - **Market Synthesizer** runs third to read the other two reports and produce the final scoring.
2. **Self-Correction:** After all three agents report back, the Supervisor invokes a lightweight LLM call to evaluate the final synthesized data. If the output lacks depth, the Supervisor can re-route the flow back to a specific agent.

## The Skills System

Agents do not use hardcoded prompts hidden in Python strings. Instead, their entire behavior, persona, and system prompt are defined in Markdown files inside the `skills/` directory.

- `skills/geopolitical-analyst/SKILL.md`
- `skills/credit-evaluator/SKILL.md`
- `skills/market-synthesizer/SKILL.md`
- `skills/supervisor/SKILL.md`

## Tools & Integrations

Each agent accesses specific tools equipped with strict Pydantic schemas.

- **Market Data:** Fetched in real-time via Yahoo Finance (`yfinance`).
- **News/Web Search:** Aggregated using DuckDuckGo (`ddgs`).
- **Hybrid RAG:** A custom retrieval pipeline using **pgvector** (semantic search via PostgreSQL) and BM25 (keyword search). The results are fused using Reciprocal Rank Fusion (RRF). Seed PDFs are located in `data/docs/`.

## Embeddings

Vector embeddings for the RAG pipeline run locally via **Ollama** using the [`embeddinggemma`](https://ollama.com/library/embeddinggemma) model (300M params, Google Gemma 3, 100+ languages).

This eliminates the need for `sentence-transformers` and `torch` (~2GB of dependencies). The embedding model runs in the same Ollama instance as the LLM.

To switch back to HuggingFace `all-MiniLM-L6-v2`, edit `config/deepagents.toml`:

```toml
[embeddings]
default = "huggingface"  # instead of "ollama"
```

## Persistence & RL Feedback Loop

- **PostgreSQL + pgvector:** All reports, news sources, RL feedback, and vector embeddings are stored in a single **PostgreSQL** instance with the `pgvector` extension. This replaces the previous SQLite + ChromaDB setup. When `DATABASE_URL` is not set, the system falls back to SQLite automatically.
- **State Checkpointing:** The LangGraph state is continuously saved to **Redis** via `langgraph-checkpoint-redis`. This allows for long-running workflows to be paused, resumed, or debugged.
- **Reinforcement Learning (RL):** In the Streamlit UI, users can vote "Useful" or "Poor" on the news sources the AI used. These votes adjust the `rl_weight` of those sources dynamically. Combined with a time decay algorithm (newer articles get a bonus), the system continuously learns which sources yield the best risk reports.

## Configuration

All infrastructure is configured via `config/deepagents.toml`:

```toml
[models.providers.ollama]
models = ["qwen3.5", "lfm2"]

[embeddings]
default = "ollama"                    # or "huggingface"

[embeddings.providers.ollama]
model = "embeddinggemma"

[vector_store]
provider = "pgvector"              # or "chroma" (local fallback)

[retrieval]
strategy = "hybrid"
vector_weight = 0.6
bm25_weight = 0.4
```

## Frontend UI

The UI is built with Streamlit (`app.py`). It features:
- A professional, high-contrast monochrome design.
- Animated pill-shaped buttons for the RL feedback loop.
- Plotly radar charts for risk breakdown (Geo, Credit, Market, ESG).
- A "Score Over Time" historical line chart tracking the risk of an entity across multiple reports.

## Logging

All pipeline events, LLM tool calls, and execution steps are cleanly logged using `loguru`.

---

## Installation

Install Python dependencies:

```sh
pip install -r requirements.txt
```

Start infrastructure services (PostgreSQL + Redis):

```sh
just services
```

Or manually:

```sh
docker compose up postgres redis -d
```

Pull the required Ollama models:

```sh
ollama pull qwen3.5
ollama pull embeddinggemma
```

## Quick Start

Launch the Streamlit frontend:

```sh
just dev
```

Or manually:

```sh
python3 -m streamlit run app.py
```

To use Gemini, select it from the sidebar dropdown and either:
- Paste your Google API key in the password field, or
- Set `GOOGLE_API_KEY` in your `.env` file (see `.env.example`)

## Environment Variables

| Variable | Required for | Description |
|----------|--------------|-------------|
| `GOOGLE_API_KEY` | Gemini | Your Google AI API key |
| `OLLAMA_MODEL` | Ollama | Model name (e.g. `qwen3.5`, `lfm2`) |
| `OLLAMA_BASE_URL` | Ollama | Base URL (default: `http://localhost:11434`) |
| `DATABASE_URL` | PostgreSQL | Connection string (default: `postgresql://risk:riskpass@localhost:5432/riskanalysis`) |
| `REDIS_URL` | Redis checkpointing | Redis connection string (default: `redis://localhost:6379`) |

## License

This project is licensed under the MIT License.