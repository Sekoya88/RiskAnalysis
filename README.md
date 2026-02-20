# Agentic LLM Framework for Credit & Geopolitical Risk Assessment

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0-green.svg)](https://github.com/langchain-ai/langgraph)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-orange.svg)](https://ai.google.dev/)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io)

A modular **multi-agent framework** leveraging **LangGraph** and the **ReAct reasoning pattern** to orchestrate LLMs for complex, multi-step financial risk evaluations.

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    SUPERVISOR (Router)                       │
│            LLM-based dynamic task delegation                 │
│         Gemini 2.5 Flash · Structured Output                │
└──────┬──────────────┬───────────────┬───────────────────────┘
       │              │               │
       ▼              ▼               ▼
┌──────────────┐ ┌───────────────┐ ┌──────────────────┐
│ Geopolitical │ │ Credit Risk   │ │ Market           │
│ Analyst      │ │ Evaluator     │ │ Synthesizer      │
│              │ │               │ │                  │
│ • DuckDuckGo │ │ • Yahoo Fin.  │ │ • Cross-ref      │
│ • News APIs  │ │ • RAG Pipeline│ │ • Risk Scoring   │
│ • RAG Search │ │ • Web Search  │ │ • Final Report   │
└──────────────┘ └───────────────┘ └──────────────────┘
       │              │               │
       └──────────────┴───────────────┘
                      │
              ┌───────▼────────┐
              │   ChromaDB     │     ┌──────────────┐
              │  Vector Store  │     │    Redis      │
              │  (RAG/Embeds)  │     │  Checkpoint   │
              └────────────────┘     └──────────────┘
```

## Stack

| Component             | Technology                                              |
| --------------------- | ------------------------------------------------------- |
| **Orchestration**     | LangGraph 1.0 (StateGraph, conditional routing)         |
| **LLM**              | Google Gemini 2.5 Flash via `langchain-google-genai`    |
| **Reasoning Pattern** | ReAct (Thought → Action → Observation loop)             |
| **State Management**  | Redis 7 via `langgraph-checkpoint-redis`                |
| **Vector DB / RAG**   | ChromaDB + HuggingFace `all-MiniLM-L6-v2` embeddings   |
| **Market Data**       | Yahoo Finance API (`yfinance`)                          |
| **News / Search**     | DuckDuckGo Search API                                   |
| **Containerization**  | Docker + Docker Compose                                 |
| **Async Runtime**     | Python `asyncio`                                        |

## Quick Start

### 1. Local Development

```bash
# Clone & setup
cd RiskAnalysis
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure: edit .env with your GOOGLE_API_KEY
# Get a key at: https://aistudio.google.com/apikey

# Run (in-memory state)
python -m src.main

# Run with custom query
python -m src.main "Assess credit risk for Tesla Inc."
```

### 2. Docker (with Redis)

```bash
# Build & run
docker compose up --build

# Or run in background
docker compose up -d --build
docker compose logs -f app
```

## Project Structure

```text
RiskAnalysis/
├── src/
│   ├── agents/
│   │   ├── prompts.py        # Specialist system prompts (ReAct)
│   │   ├── nodes.py          # LangGraph node functions
│   │   └── supervisor.py     # LLM-based dynamic router
│   ├── tools/
│   │   ├── market_data.py    # Yahoo Finance integration
│   │   ├── news_api.py       # DuckDuckGo News + Web search
│   │   └── rag_pipeline.py   # ChromaDB RAG pipeline
│   ├── state/
│   │   └── schema.py         # AgentState TypedDict schema
│   ├── graph.py              # LangGraph builder + Redis checkpoint
│   └── main.py               # Async entrypoint
├── data/                     # ChromaDB persistence
├── output/                   # Generated risk reports
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                      # API keys (git-ignored)
```

## Agents

| Agent                  | Role                                                      | Tools                            |
| ---------------------- | --------------------------------------------------------- | -------------------------------- |
| **Supervisor**         | Routes tasks, prevents loops, decides completion          | Structured LLM output            |
| **Geopolitical Analyst** | Macro & geopolitical risk assessment                    | News API, Web Search, RAG        |
| **Credit Risk Evaluator** | Quantitative & qualitative credit analysis             | Market Data, RAG, Web Search     |
| **Market Synthesizer**  | Final integrated risk report (CRO-level)                 | RAG, Web Search                  |

## Output

The framework produces a structured **Integrated Risk Assessment Report** with:

- Overall Risk Score (0-100)
- Risk decomposition (Geopolitical, Credit, Market, ESG)
- Scenario analysis (Bull/Base/Bear with probabilities)
- Actionable recommendations

Reports are saved to `output/risk_report_YYYYMMDD_HHMMSS.md`.

---

**Stack**: Python 3.13 · LangGraph · Gemini 2.5 Flash · ChromaDB · Redis · Docker · Asyncio
