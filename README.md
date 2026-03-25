# Agentic Risk Assessment Framework (Backend API)

Evaluate geopolitical, credit, and market risks using an AI multi-agent system built with **LangGraph** and **FastAPI**.

[![Build Status](https://github.com/user/repo/workflows/build/badge.svg)](https://github.com/user/repo/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)

> **Note:** This repository contains the **Backend API** and the **Agentic Framework**. 
> The modern Next.js 14 frontend is located in a separate repository: [RiskAnalysis-UI](https://github.com/Sekoya88/RiskAnalysis-UI).

## Overview

This project is an advanced multi-agent risk assessment pipeline. It leverages specialized AI agents capable of reasoning, researching, and synthesizing financial risk reports. The backend is exposed via a **FastAPI** REST interface with **WebSocket** support for real-time agent execution logs.

You can run this framework entirely locally using **Ollama** or switch instantly to Google's **Gemini 2.5 Flash** via API for faster, production-grade reasoning.

## Architecture (Clean DDD & API-First)

The system follows a **Domain-Driven Design** with clear separation of concerns, operating as a decoupled API for any client:

```text
src/
├── api.py                  # FastAPI application & WebSocket broadcaster
├── main.py                 # LangGraph execution entrypoint
├── domain/                 # Pure business logic, zero external deps
│   ├── models/             # RiskReport, Scenario, Source (value objects)
│   ├── ports/              # Protocol interfaces (LLM, Embedding, VectorStore, etc.)
│   └── services/           # RL scoring, report parsing
├── application/            # Orchestration layer
│   ├── agents/             # Geopolitical, Credit, Synthesizer (ReAct loop)
│   ├── supervisor.py       # Pipeline routing + self-correction
│   └── graph.py            # LangGraph StateGraph builder
├── infrastructure/         # Concrete adapter implementations
│   ├── llm/                # OllamaLLMAdapter, GeminiLLMAdapter, factory
│   ├── embeddings/         # OllamaEmbeddingAdapter (embeddinggemma)
│   ├── vector_store/       # PgVectorStoreAdapter (PostgreSQL + pgvector)
│   ├── retrieval/          # HybridRetriever (RRF fusion)
│   ├── data_sources/       # YahooFinanceAdapter, DuckDuckGoAdapter
│   └── persistence/        # PostgreSQL (reports + RL feedback), Redis (memory)
└── container.py            # Dependency injection (composition root)
```

## The Frontend (Next.js)

The UI can live in a **sibling folder** (e.g. `../riskanalysis-ui` next to this repo) or in the separate **[RiskAnalysis-UI](https://github.com/Sekoya88/RiskAnalysis-UI)** repository.

It features a high-contrast monochrome design, WebSocket log streaming, markdown reports, optional **metrics labels** (ground truth), and a **runtime bar** (DB Postgres/SQLite + PPO on/off via `GET /api/runtime-info`, checkpoint par défaut `data/ppo_source_policy.pt`, désactivable avec `PPO_DISABLED=1`).

See also **`CODEBASE_CONTEXT.md`** in this repo for an architecture snapshot.

## Multi-Agent Flow

The system runs a LangGraph state machine directed by a **Supervisor Agent**.

1. **Deterministic Routing:** The Supervisor enforces a strict pipeline.
   - **Geopolitical Analyst** runs first to search global news and assess macro risks.
   - **Credit Risk Evaluator** runs second to fetch market data and assess financial health.
   - **Market Synthesizer** runs third to read the other two reports and produce the final scoring.
2. **Self-Correction:** After all three agents report back, the Supervisor invokes a lightweight LLM call to evaluate the final synthesized data. If the output lacks depth, the Supervisor can re-route the flow back to a specific agent.

## Tools & Persistence

- **Tools:** Agents access real-time market data (`yfinance`), web search (`duckduckgo`), and a custom **Hybrid RAG** pipeline (pgvector + BM25 with Reciprocal Rank Fusion).
- **PostgreSQL + pgvector:** All reports, news sources, RL feedback, and vector embeddings are stored in PostgreSQL.
- **State Checkpointing:** The LangGraph state is continuously saved to **Redis** via `langgraph-checkpoint-redis`.
- **Reinforcement Learning (RL):** The system continuously learns which sources yield the best risk reports based on user feedback (via API).

---

## Getting Started

### 1. Prerequisites

- Python 3.11+
- Node.js 20+ (for the frontend)
- Docker Desktop (for Postgres and Redis)
- [Ollama](https://ollama.com/) (for local models)
- [Just](https://github.com/casey/just) command runner (optional but recommended)

### 2. Run the Backend API

Clone this repository and set up the environment:

```sh
git clone https://github.com/Sekoya88/RiskAnalysis.git
cd RiskAnalysis

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Optional — use the repo Git hooks so commit messages are not polluted with `Made-with: Cursor` trailers:

```sh
just git-hooks
```

Start the infrastructure (PostgreSQL and Redis) via Docker:

```sh
docker compose up postgres redis -d
```

**Postgres Docker : port host `15432` par défaut** (`POSTGRES_PORT_PUBLISH` dans `.env`). Évite à la fois le Postgres local (`5432`) et d’autres services sur `5433`. Dans `.env`, garde le **même** port dans `DATABASE_URL` et `POSTGRES_PORT_PUBLISH`.

Si Docker affiche `Bind for 0.0.0.0:15432 failed: port is already allocated`, choisis un port libre (ex. `5434`) dans `.env` pour les deux variables, puis `docker compose up -d postgres redis`.

Si tu vois `FATAL: role "risk" does not exist`, `DATABASE_URL` pointe vers la mauvaise instance : vérifie le port. Pour repartir à zéro côté Docker : `docker compose down -v` puis `docker compose up postgres redis -d`.

Pull the required local AI models via Ollama:

```sh
ollama pull qwen3.5
ollama pull lfm2
ollama pull embeddinggemma
```

Copy the environment variables template:

```sh
cp .env.example .env
```
*(Optional: Add your `GOOGLE_API_KEY` in `.env` if you want to use Gemini).*

Start the FastAPI server:

```sh
just backend    # Docker deps + crée data/ppo_source_policy.pt si torch + fichier absent, puis uvicorn
# ou: just dev   (sans Docker stack ni PPO ensure)
# ou: uvicorn src.api:app --reload
```
The API will be available at `http://127.0.0.1:8000`.

**PPO** (scores des sources, pas le LLM) : par défaut le backend charge **`data/ppo_source_policy.pt`** s’il existe. Avec **`pip install -r requirements-rl.txt`**, **`just backend`** lance automatiquement l’entraînement **skip-if-exists** avant uvicorn (équivalent **`just ppo-ensure`**). Manuellement : **`just ppo-ensure`**.

Désactiver : **`PPO_DISABLED=1`** dans `.env`. Autre fichier : **`PPO_SOURCE_POLICY_PATH=/chemin/vers.pt`** (prioritaire sur le défaut).

### 3. Run the Frontend UI

From a **sibling checkout** (example: `RiskAnalysis` and `riskanalysis-ui` in the same parent directory):

```sh
cd ../riskanalysis-ui   # adjust path if needed
npm install
just dev
# Or: npm run dev -- -H 127.0.0.1
```

Or clone the standalone UI repo as in the original instructions. Open [http://127.0.0.1:3000](http://127.0.0.1:3000).

If the API is not on localhost, set in `riskanalysis-ui/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8000
```

The UI polls `GET /api/runtime-info` to show **Postgres vs SQLite** and **PPO on/off**.

## Observability

The framework ships with dual observability out of the box.

### Langfuse (self-hosted, open-source)

Tracks every LLM call with token counts, costs, and session grouping. Runs entirely locally — no data leaves your machine.

```sh
just db-langfuse    # une fois : crée la base `langfuse` dans le conteneur Postgres
just langfuse-up    # ou : docker compose up postgres redis langfuse -d
# UI → http://localhost:3001
# Create a project, copy the keys into .env (LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY)
# LANGFUSE_HOST=http://localhost:3001
```

Connexion SQL (Beekeeper, etc.) : voir **`docs/BEEKEEPER.md`**.

> **Note:** Uses a custom `LangfuseV2Callback` (compatible with Langfuse server v2.x OSS).
> The official SDK v3/v4 sends traces via OpenTelemetry which is only supported by Langfuse server v3+.

### LangSmith (cloud, LangChain native)

Traces the full LangGraph execution graph: every node, edge, LLM call, and tool call — automatically, with zero extra code.

```sh
# 1. Get a key at https://smith.langchain.com → Settings → API Keys
# 2. In .env:
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=RiskAnalysis
```

|                          | Langfuse                  | LangSmith                        |
| ------------------------ | ------------------------- | -------------------------------- |
| **Hosting**              | Self-hosted (free)        | Cloud (free tier)                |
| **Integration**          | Custom callback           | Native LangChain env vars        |
| **LangGraph visibility** | LLM calls only            | Full graph: nodes, edges, states |
| **Best for**             | Production, privacy       | Debugging, evaluation            |

---

## License

This project is licensed under the MIT License.
