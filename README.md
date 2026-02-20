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
              ┌───────▼────────┐     ┌──────────────┐
              │   ChromaDB     │     │    Redis      │
              │  Vector Store  │     │  Checkpoint   │
              │  (RAG/Embeds)  │     └──────────────┘
              └────────────────┘
```

## Stack

| Component | Technology |
| :--- | :--- |
| **Orchestration** | LangGraph 1.0 (StateGraph, conditional routing) |
| **LLM** | Google Gemini 2.5 Flash via `langchain-google-genai` |
| **Reasoning Pattern** | ReAct (Thought → Action → Observation loop) |
| **State Management** | Redis 7 via `langgraph-checkpoint-redis` |
| **Vector DB / RAG** | ChromaDB + HuggingFace `all-MiniLM-L6-v2` embeddings |
| **Market Data** | Yahoo Finance API (`yfinance`) |
| **News / Search** | DuckDuckGo Search API |
| **Web Interface** | Streamlit + Plotly |
| **Containerization** | Docker + Docker Compose |
| **Observability** | LangSmith (tracing LLM calls) |
| **Async Runtime** | Python `asyncio` |

---

## Comment ça fonctionne — Explication technique

### 1. Le pipeline d'agents

Quand tu lances une requête (ex: "Évaluer le risque de NVIDIA"), voici ce qui se passe :

```text
Ta requête
    │
    ▼
[SUPERVISOR] → Décide : "Le Geopolitical Analyst doit commencer"
    │
    ▼
[GEOPOLITICAL ANALYST]
    │ Réfléchit (ReAct loop) :
    │   1. "Je dois chercher les tensions US-Chine sur les puces IA"
    │   2. Appelle l'outil search_geopolitical_news("NVIDIA export controls China")
    │   3. Lit les résultats, réfléchit encore
    │   4. Appelle search_corporate_disclosures("NVIDIA geopolitical risk")
    │   5. Synthétise son analyse géopolitique
    │
    ▼
[SUPERVISOR] → Décide : "Le Credit Evaluator doit continuer"
    │
    ▼
[CREDIT RISK EVALUATOR]
    │   1. Appelle get_market_data("NVDA") → récupère prix, P/E, dette live
    │   2. Appelle search_corporate_disclosures("NVIDIA financial health")
    │   3. Calcule Z-Score, analyse les ratios
    │   4. Produit son évaluation crédit
    │
    ▼
[SUPERVISOR] → Décide : "Le Market Synthesizer doit conclure"
    │
    ▼
[MARKET SYNTHESIZER]
    │   Lit les analyses des 2 agents précédents
    │   Croise les données, produit le rapport final
    │   Score de risque intégré (0-100) + scénarios + recommandations
    │
    ▼
📊 RAPPORT FINAL sauvegardé dans output/
```

### 2. Le pattern ReAct — Comment un agent "réfléchit"

Chaque agent utilise le pattern **ReAct** (Reasoning + Acting). Concrètement, le LLM alterne entre :

1. **Thought** (Réflexion) — "Je dois trouver les données financières de NVIDIA"
2. **Action** (Outil) — Appelle `get_market_data("NVDA")`
3. **Observation** — Reçoit les données : prix, P/E, dette, etc.
4. **Thought** — "Le P/E est de 65, c'est élevé. Je dois aussi vérifier…"
5. **Action** — Appelle un autre outil
6. Répète jusqu'à avoir assez d'informations (max 6 itérations)

Le code de cette boucle est dans `src/agents/nodes.py` → `_run_react_loop()`.

### 3. RAG — Retrieval-Augmented Generation

**Problème** : Le LLM a une date de coupure d'entraînement. Il ne connaît pas les derniers rapports financiers et il peut "halluciner" (inventer des chiffres).

**Solution** : Le RAG permet au LLM de **chercher dans une base de documents** avant de répondre.

#### Comment ça marche

```text
1. INDEXATION (au premier lancement)
   ┌─────────────────┐
   │ Documents texte  │  ex: "Apple Annual Report 2024: supply chain
   │ (10-K, credit    │       concentration risk in Asia-Pacific..."
   │  reports, ESG)   │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │  Modèle         │  all-MiniLM-L6-v2 (HuggingFace)
   │  d'embedding    │  Tourne en local sur le CPU
   └────────┬────────┘
            │  Transforme le texte en vecteur
            │  ex: [0.023, -0.117, 0.445, ..., 0.012]  (384 dimensions)
            ▼
   ┌─────────────────┐
   │   ChromaDB      │  Base de données vectorielle
   │   (stockage)    │  Persiste dans data/chroma_db/
   └─────────────────┘

2. RECHERCHE (à chaque requête d'agent)
   ┌─────────────────┐
   │ Requête agent :  │  "Apple supply chain risk China Taiwan"
   │ (texte libre)    │
   └────────┬────────┘
            │  Même embedding
            ▼
   ┌─────────────────┐
   │ Vecteur requête  │  [0.031, -0.098, 0.512, ...]
   └────────┬────────┘
            │  Recherche par similarité cosinus
            ▼
   ┌─────────────────┐
   │ Top-K documents  │  Les 4 documents les plus proches
   │ les + pertinents │  sémantiquement
   └────────┬────────┘
            │
            ▼
   Le LLM lit ces documents et s'en sert pour répondre
   → Moins d'hallucination, réponses ancrées dans des faits
```

#### État actuel du RAG

**OUI, le RAG est implémenté et fonctionnel.** Le code est dans `src/tools/rag_pipeline.py`.

### 4. Sources de données — Temps réel vs Statique

| Source | Type | Fraîcheur | Fichier |
| :--- | :--- | :--- | :--- |
| **DuckDuckGo News** | 🟢 Live | Actualités récentes | `src/tools/news_api.py` |
| **Yahoo Finance** | 🟢 Live | Données marché temps réel | `src/tools/market_data.py` |
| **DuckDuckGo Web** | 🟢 Live | Recherche web générale | `src/tools/news_api.py` |
| **ChromaDB RAG** | 🔴 Statique | Documents seed 2025-2026 | `src/tools/rag_pipeline.py` |

Les données **live** (news, prix d'actions) sont fraîches à chaque requête. Les documents **RAG** sont statiques et doivent être mis à jour manuellement.

### 5. LangSmith — Observabilité

LangSmith trace **chaque appel LLM** en temps réel. Pour l'utiliser :

1. Créer un compte gratuit sur [smith.langchain.com](https://smith.langchain.com)
2. Configurer dans `.env` :

   ```bash
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=lsv2_pt_xxxx...
   LANGCHAIN_PROJECT=RiskAnalysis
   ```

3. Lancer une analyse → aller sur smith.langchain.com → Projects → RiskAnalysis
4. Cliquer sur un run pour voir le graph complet, les prompts, les réponses, les outils appelés

---

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

# Run the web interface
streamlit run app.py
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
├── app.py                    # Streamlit web interface
├── src/
│   ├── agents/
│   │   ├── prompts.py        # Specialist system prompts (ReAct)
│   │   ├── nodes.py          # LangGraph node functions + ReAct loop
│   │   └── supervisor.py     # LLM-based dynamic router
│   ├── tools/
│   │   ├── market_data.py    # Yahoo Finance integration (live)
│   │   ├── news_api.py       # DuckDuckGo News + Web search (live)
│   │   └── rag_pipeline.py   # ChromaDB RAG pipeline (static seed)
│   ├── state/
│   │   └── schema.py         # AgentState TypedDict schema
│   ├── graph.py              # LangGraph builder + Redis checkpoint
│   └── main.py               # Async entrypoint + source extraction
├── data/                     # ChromaDB persistence
├── output/                   # Generated risk reports
├── glossaire.md              # Glossaire technique EN→FR
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                      # API keys (git-ignored)
```

## Agents

| Agent | Role | Tools |
| :--- | :--- | :--- |
| **Supervisor** | Routes tasks, prevents loops, decides completion | Structured LLM output |
| **Geopolitical Analyst** | Macro & geopolitical risk assessment | News API, Web Search, RAG |
| **Credit Risk Evaluator** | Quantitative & qualitative credit analysis | Market Data, RAG, Web Search |
| **Market Synthesizer** | Final integrated risk report (CRO-level) | RAG, Web Search |

## Output

The framework produces a structured **Integrated Risk Assessment Report** with:

- Overall Risk Score (0-100)
- Risk decomposition (Geopolitical, Credit, Market, ESG)
- Scenario analysis (Bull/Base/Bear with probabilities)
- Actionable recommendations

Reports are saved to `output/risk_report_YYYYMMDD_HHMMSS.md`.

---

**Stack**: Python 3.13 · LangGraph · Gemini 2.5 Flash · ChromaDB · Redis · Streamlit · Docker · Asyncio
