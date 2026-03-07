# Agentic LLM Framework for Credit & Geopolitical Risk Assessment

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0-green.svg)](https://github.com/langchain-ai/langgraph)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-purple.svg)](https://ollama.com)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io)

A modular **multi-agent framework** leveraging **LangGraph** and the **ReAct reasoning pattern** to orchestrate local LLMs (via Ollama) for complex, multi-step financial risk evaluations.

Powered by the **DeepAgents Skills** system: agent behaviors are defined in editable SKILL.md files, not hardcoded prompts.

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    SUPERVISOR (Router)                       │
│      Deterministic pipeline + LLM-based self-correction     │
│              Ollama (qwen3.5 / lfm2) · Skills               │
└──────┬──────────────┬───────────────┬───────────────────────┘
       │              │               │
       ▼              ▼               ▼
┌──────────────┐ ┌───────────────┐ ┌──────────────────┐
│ Geopolitical │ │ Credit Risk   │ │ Market           │
│ Analyst      │ │ Evaluator     │ │ Synthesizer      │
│              │ │               │ │                  │
│ • DuckDuckGo │ │ • Yahoo Fin.  │ │ • Cross-ref      │
│ • News APIs  │ │ • RAG(Hybrid) │ │ • Risk Scoring   │
│ • RAG(Hybrid)│ │ • Web Search  │ │ • Final Report   │
└──────────────┘ └───────────────┘ └──────────────────┘
       │              │               │
       └──────────────┴───────────────┘
                      │
              ┌───────▼────────┐     ┌──────────────┐
              │   ChromaDB     │     │    Redis      │
              │  Vector Store  │     │  Checkpoint   │
              │ + BM25 (Hybrid)│     └──────────────┘
              └────────────────┘
```

## Stack

| Component | Technology |
| :--- | :--- |
| **Orchestration** | LangGraph 1.0 (StateGraph, conditional edges, `add_messages` reducer) |
| **LLM** | Ollama local inference — `qwen3.5` (9B, fast) / `lfm2` (24B, strong reasoning) |
| **Skills System** | DeepAgents SKILL.md files — editable agent behaviors without code changes |
| **Provider Config** | `config/deepagents.toml` — per-model overrides (temperature, context, predict) |
| **Reasoning Pattern** | ReAct (Thought → Action → Observation loop, max 6 iterations) |
| **State Management** | Redis 7 via `langgraph-checkpoint-redis` (fallback: `MemorySaver`) + SQLite (`risk_history.db`) |
| **Vector DB / RAG** | ChromaDB + HuggingFace `all-MiniLM-L6-v2` embeddings + BM25 keyword search |
| **Hybrid Retrieval** | Reciprocal Rank Fusion (60% semantic / 40% BM25) |
| **Market Data** | Yahoo Finance API (`yfinance`) — live prices, ratios, balance sheet |
| **News / Search** | DuckDuckGo Search API (`ddgs`) — news + web search |
| **PDF Ingestion** | `pypdf` — loads PDFs from `data/docs/` into ChromaDB at startup |
| **Web Interface** | Streamlit + Plotly (radar charts, risk visualisation, historical graphs) |
| **ML Feedback Loop** | Reinforcement Learning using SQLite to weight news sources with time decay |
| **Containerization** | Docker + Docker Compose |
| **Observability** | LangSmith (tracing LLM calls) + per-agent token tracking |

---

## Quick Start

### Prerequisites

- **Ollama** running locally on port 11434 (`brew install ollama && brew services start ollama`)
- **Docker** (for Redis Stack)
- **just** command runner (`brew install just`)

### Launch

```bash
# Install dependencies
pip install -r requirements.txt

# Pull models + start Redis + launch Streamlit
just dev
```

This will:
1. Start Redis Stack via Docker (`docker compose up redis -d`)
2. Pull `qwen3.5` and `lfm2` models via Ollama
3. Launch the Streamlit UI at http://localhost:8501

Select the model from the Streamlit sidebar.

### CLI Mode

```bash
just cli "Assess risk for Tesla (TSLA)"
just cli --redis "Assess risk for Apple (AAPL)"
```

### Docker (full stack)

```bash
just start
```

---

## Available Models

| Model    | Size | Strengths              | Config |
|----------|------|------------------------|--------|
| qwen3.5  | 9B   | Fast, good tool-use    | temp=0.1, ctx=8192, predict=4096 |
| lfm2     | 24B  | Strong reasoning       | temp=0.15, ctx=16384, predict=8192 |

Per-model parameters are in `config/deepagents.toml`.

---

## Skills System

Agent behaviors are defined as **SKILL.md** files following the [Agent Skills specification](https://agentskills.io/specification), not hardcoded prompt strings.

```
skills/
├── geopolitical-analyst/SKILL.md   # Geopolitical & macro-economic risk analysis
├── credit-evaluator/SKILL.md       # Quantitative & qualitative credit evaluation
├── market-synthesizer/SKILL.md     # Final integrated risk report synthesis
└── supervisor/SKILL.md             # Pipeline orchestration & self-correction
```

Each SKILL.md has:
- **YAML frontmatter**: name, description, allowed-tools, metadata
- **Markdown body**: instructions the agent follows

To modify an agent's behavior, edit its SKILL.md — no code changes needed. Skills are loaded via `src/agents/skills.py` with LRU caching.

---

## Project Structure

```text
RiskAnalysis/
├── skills/                       # DeepAgents Skills (agent behaviors)
│   ├── geopolitical-analyst/SKILL.md
│   ├── credit-evaluator/SKILL.md
│   ├── market-synthesizer/SKILL.md
│   └── supervisor/SKILL.md
├── config/
│   └── deepagents.toml           # Ollama per-model overrides
├── src/
│   ├── agents/
│   │   ├── skills.py             # Skill loader (parses SKILL.md → Skill dataclass)
│   │   ├── nodes.py              # LangGraph agent nodes + ReAct loop + token tracking
│   │   └── supervisor.py         # Hybrid routing: deterministic + LLM self-correction
│   ├── config/
│   │   └── providers.py          # Per-model config reader (deepagents.toml)
│   ├── tools/
│   │   ├── market_data.py        # Yahoo Finance (prix, ratios, bilan, historique)
│   │   ├── news_api.py           # DuckDuckGo News + Web search + RL weighting
│   │   └── rag_pipeline.py       # Hybrid RAG: ChromaDB vectors + BM25 + RRF
│   ├── state/
│   │   └── schema.py             # AgentState TypedDict (messages, risk_signals, etc.)
│   ├── db.py                     # SQLite: report history + RL feedback storage
│   ├── utils.py                  # Retry avec exponential backoff + jitter
│   ├── graph.py                  # StateGraph builder + Redis/Memory checkpointing
│   └── main.py                   # Async entrypoint + source extraction + cost calc
├── app.py                        # Streamlit web interface (dashboard complet)
├── data/
│   ├── docs/                     # PDFs seed pour le RAG (WEF, Apollo, etc.)
│   └── chroma_db/                # ChromaDB persistence (auto-generated)
├── output/                       # Generated reports (Markdown)
├── justfile                      # Build automation (just dev / just cli / just start)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                          # Config (git-ignored)
```

---

## Comment ca fonctionne

### 1. Le pipeline d'agents

```text
Ta requete
    │
    ▼
[SUPERVISOR] → Pipeline deterministe : route vers le premier agent non execute
    │
    ▼
[GEOPOLITICAL ANALYST]
    │ Boucle ReAct (max 6 iterations) :
    │   1. "Je dois chercher les tensions US-Chine sur les puces IA"
    │   2. Appelle search_geopolitical_news("NVIDIA export controls China")
    │   3. Lit les resultats, reflechit encore
    │   4. Appelle search_corporate_disclosures("NVIDIA geopolitical risk")
    │   5. Synthetise son analyse geopolitique
    │   → Resultat stocke dans risk_signals[] + messages prunes
    │
    ▼
[SUPERVISOR] → Verifie risk_signals : credit_evaluator n'a pas encore reporte
    │
    ▼
[CREDIT RISK EVALUATOR]
    │   1. Appelle get_market_data("NVDA") → prix, P/E, dette, ratios live
    │   2. Appelle search_corporate_disclosures("NVIDIA financial health")
    │   3. Calcule Z-Score, analyse les ratios, notation credit interne
    │   4. Produit son evaluation credit
    │
    ▼
[SUPERVISOR] → market_synthesizer n'a pas encore reporte
    │
    ▼
[MARKET SYNTHESIZER]
    │   Lit les analyses des 2 agents via risk_signals (pas les messages bruts)
    │   Croise les donnees, produit le rapport final
    │   Score de risque integre (0-100) + sous-scores + scenarios
    │
    ▼
[SUPERVISOR] → Evaluation qualite par LLM (self-correction)
    │   Lit UNIQUEMENT les risk_signals (~2.5K tokens vs ~50K)
    │   Si OK → FINISH
    │   Si lacune → re-route vers l'agent concerne
    │
    ▼
Rapport final sauvegarde dans output/risk_report_YYYYMMDD_HHMMSS.md
```

### 2. Supervisor — Routage hybride

Le supervisor combine deux strategies (`src/agents/supervisor.py`) :

1. **Routage deterministe** — Tant que les 3 agents n'ont pas tous reporte, le supervisor suit l'ordre fixe. Aucun appel LLM, zero token.
2. **Self-correction par LLM** — Une fois tous les agents passes, le supervisor charge le skill `supervisor/SKILL.md` et evalue la qualite via `risk_signals[]`. S'il detecte une lacune, il re-route.

Guard : `iteration_count >= 10` empeche toute boucle infinie.

### 3. RAG Hybride (Vector + BM25)

```text
Requete agent : "Apple supply chain risk China Taiwan"
    │
    ├──── Recherche semantique (60%)          ├──── BM25 mots-cles (40%)
    │     ChromaDB + all-MiniLM-L6-v2         │     Correspondance exacte
    │     → Top-K resultats                    │     → Top-K resultats
    │                                          │
    └────────────────┬─────────────────────────┘
                     │
                     ▼
           Reciprocal Rank Fusion (k=60)
           Score = Σ weight × (1 / (k + rank))
                     │
                     ▼
           Top documents fusionnes et re-classes
```

Documents seed dans `data/docs/` sont indexes automatiquement au premier lancement.

### 4. Boucle de Feedback ML (RL)

1. L'utilisateur vote sur chaque source dans l'UI Streamlit
2. Votes stockes dans SQLite (`data/risk_history.db`)
3. Au prochain run, les sources avec score < 0.20 sont filtrees
4. Time Decay : articles recents recoivent un bonus

### 5. Optimisations Token

| Optimisation | Gain | Fichier |
| :--- | :--- | :--- |
| **Message Pruning** | ~40-50% tokens/run | `nodes.py` → `_prune_messages()` |
| **Supervisor leger** | ~95% sur l'evaluation | `supervisor.py` → `risk_signals` |
| **Per-model config** | Context optimise par modele | `config/deepagents.toml` |

---

## Output

The framework produces a structured **Integrated Risk Assessment Report** with:

* Overall Risk Score (0-100)
* Risk decomposition (Geopolitical, Credit, Market, ESG)
* Internal Credit Rating (AAA-D) with outlook
* Scenario analysis (Bull/Base/Bear with probabilities)
* Actionable recommendations
* Source citations

Reports are saved to `output/risk_report_YYYYMMDD_HHMMSS.md`.

---

**Stack**: Python 3.13 · LangGraph · Ollama (qwen3.5/lfm2) · DeepAgents Skills · ChromaDB · BM25/RRF · Redis · Streamlit · Plotly · Docker
