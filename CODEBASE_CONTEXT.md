# Codebase Context: RiskAnalysis (local repository)

> **Scope:** This report is built from **this repo only** (no org-wide code search). Cross-check `git log` and open PRs for freshness.

## Freshness check


| Area                                            | Notes                               | Status                             |
| ----------------------------------------------- | ----------------------------------- | ---------------------------------- |
| Backend (`src/`, `evaluation/`)                 | Active LangGraph + FastAPI patterns | **Active** (verify with `git log`) |
| UI (`../riskanalysis-ui` sibling)               | Next.js 16 App Router               | **Active**                         |
| Docs (`metric.md`, `technique.md`)              | Product/architecture notes          | **Current** — compare with code    |


## Overview

**RiskAnalysis** is a **multi-agent** geopolitical / credit / market risk pipeline built on **LangGraph**, exposed via **FastAPI** (`src/api.py`) with **WebSocket** log streaming. Agents use tools (DuckDuckGo news, yfinance, hybrid RAG over **pgvector** + BM25). After a run, the API enriches **sources** with **per-URL scores**: human **feedback** from Postgres/SQLite, **recency** (`compute_rl_weight` in `src/domain/services/risk_scoring.py`), and an optional **PPO** nudge if `PPO_SOURCE_POLICY_PATH` is set (`src/rl/`). The **LLM is not fine-tuned**; only **context selection** (top-k news/RAG) changes. The **evaluation** package traces runs and can compute optional metrics when **ground-truth labels** are sent on `POST /api/analyze` (`metrics_`* fields).

## Key “repositories” (layout)


| Path                         | Purpose                                             |
| ---------------------------- | --------------------------------------------------- |
| `RiskAnalysis/` (this repo)  | Backend, agents, DB adapters, optional PPO training |
| `riskanalysis-ui/` (sibling) | Next.js dashboard, CommandBar, ReportView, sidebars |


## Architecture highlights

- **API layer:** `src/api.py` — `POST /api/analyze`, `POST /api/feedback`, `GET /api/runtime-info`, `WS /api/ws/stream`.
- **Orchestration:** `src/main.py` — `run_analysis()` builds LangGraph, optional `trace_sink`, post-processes `sources` (scores, sort, `[:10]`).
- **Domain:** `src/domain/` — ports (`FeedbackRepositoryPort` includes `list_feedback_votes` for PPO training), `risk_scoring`.
- **Infrastructure:** `src/infrastructure/persistence/` — Postgres + SQLite feedback/reports; `data_sources/duckduckgo.py` uses same scoring path as `main.py`.
- **RL / PPO:** `src/rl/train_ppo_sources.py`, `inference.py` — optional; `requirements-rl.txt` + `just ppo-train`.
- **Evaluation:** `evaluation/` — `RunTraceCollector`, `compute_metric_scores_with_report`, `metric.md` describes UX and RL semantics.

## Documentation (vetted, local)


| Doc                   | Role                                                     |
| --------------------- | -------------------------------------------------------- |
| `README.md`           | Backend setup, Docker Postgres/Redis, Ollama, `just dev` |
| `metric.md`           | Métriques, RLHF par URL, PPO, ground truth API           |
| `CODEBASE_CONTEXT.md` | This file                                                |


## Key contributors

Not available from this workspace (no org directory). Use `git shortlog -sn` in-repo.

## Related systems (external)

- **Ollama** — local LLMs (`qwen3.5`, etc.).
- **Google GenAI** — optional cloud model via env / `CommandBar` model id.
- **Redis** — LangGraph checkpointer (`use_redis` on analyze).
- **PostgreSQL** — reports, feedback, pgvector when `DATABASE_URL` set.

## Warnings

- **UI `report_id` for feedback:** sidebar/report thumbs may send a **client run id**; backend expects a `report_id` compatible with your DB usage — align with `thread_id` from analyze response if you need strict FK to `reports`.
- **PPO:** Requires `torch` + training data; without checkpoint, behavior is heuristic + votes only.
- **Stale docs:** Root `README.md` still references a **separate GitHub UI repo**; if you use a **local sibling** `riskanalysis-ui/`, follow local paths in the README section added during your setup.

## Suggested entry points (code)

1. `src/api.py` — HTTP + WS contract.
2. `src/main.py` — graph run + source scoring loop.
3. `src/domain/services/risk_scoring.py` — `compute_rl_weight`.
4. `riskanalysis-ui/src/hooks/useRiskAnalysis.ts` — analyze + websocket client.

