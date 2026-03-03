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
│      Deterministic pipeline + LLM-based self-correction     │
│           Gemini 2.5 Flash · JSON Structured Output         │
└──────┬──────────────┬───────────────┬───────────────────────┘
       │              │               │
       ▼              ▼               ▼
┌──────────────┐ ┌───────────────┐ ┌──────────────────┐
│ Geopolitical │ │ Credit Risk   │ │ Market           │
│ Analyst      │ │ Evaluator     │ │ Synthesizer      │
│              │ │               │ │                  │
│ • DuckDuckGo │ │ • Yahoo Fin.  │ │ • Cross-ref      │
│ • News APIs  │ │ • RAG (Hybrid)│ │ • Risk Scoring   │
│ • RAG (Hybrid│ │ • Web Search  │ │ • Final Report   │
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
| **LLM** | Google Gemini 2.5 Flash via `langchain-google-genai` |
| **Reasoning Pattern** | ReAct (Thought → Action → Observation loop, max 6 iterations) |
| **State Management** | Redis 7 via `langgraph-checkpoint-redis` (fallback: `MemorySaver`) |
| **Vector DB / RAG** | ChromaDB + HuggingFace `all-MiniLM-L6-v2` embeddings + BM25 keyword search |
| **Hybrid Retrieval** | Reciprocal Rank Fusion (60% semantic / 40% BM25) |
| **Market Data** | Yahoo Finance API (`yfinance`) — live prices, ratios, balance sheet |
| **News / Search** | DuckDuckGo Search API (`ddgs`) — news + web search |
| **PDF Ingestion** | `pypdf` — loads PDFs from `data/docs/` into ChromaDB at startup |
| **Web Interface** | Streamlit + Plotly (radar charts, risk visualisation) |
| **Containerization** | Docker + Docker Compose |
| **Observability** | LangSmith (tracing LLM calls) + per-agent token tracking |
| **Async Runtime** | Python `asyncio` |

---

## Comment ça fonctionne — Explication technique

### 1. Le pipeline d'agents

Quand tu lances une requête (ex: "Évaluer le risque de NVIDIA"), voici ce qui se passe :

```text
Ta requête
    │
    ▼
[SUPERVISOR] → Pipeline déterministe : route vers le premier agent non exécuté
    │
    ▼
[GEOPOLITICAL ANALYST]
    │ Boucle ReAct (max 6 itérations) :
    │   1. "Je dois chercher les tensions US-Chine sur les puces IA"
    │   2. Appelle search_geopolitical_news("NVIDIA export controls China")
    │   3. Lit les résultats, réfléchit encore
    │   4. Appelle search_corporate_disclosures("NVIDIA geopolitical risk")
    │   5. Synthétise son analyse géopolitique
    │   → Résultat stocké dans risk_signals[] + messages prunés
    │
    ▼
[SUPERVISOR] → Vérifie risk_signals : credit_evaluator n'a pas encore reporté
    │
    ▼
[CREDIT RISK EVALUATOR]
    │   1. Appelle get_market_data("NVDA") → prix, P/E, dette, ratios live
    │   2. Appelle search_corporate_disclosures("NVIDIA financial health")
    │   3. Calcule Z-Score, analyse les ratios, notation crédit interne
    │   4. Produit son évaluation crédit
    │
    ▼
[SUPERVISOR] → market_synthesizer n'a pas encore reporté
    │
    ▼
[MARKET SYNTHESIZER]
    │   Lit les analyses des 2 agents via risk_signals (pas les messages bruts)
    │   Croise les données, produit le rapport final
    │   Score de risque intégré (0-100) + sous-scores + scénarios
    │
    ▼
[SUPERVISOR] → Évaluation qualité par LLM (self-correction)
    │   Lit UNIQUEMENT les risk_signals (~2.5K tokens vs ~50K)
    │   Si OK → FINISH
    │   Si lacune → re-route vers l'agent concerné
    │
    ▼
Rapport final sauvegardé dans output/risk_report_YYYYMMDD_HHMMSS.md
```

### 2. Le Supervisor — Routage hybride

Le supervisor combine **deux stratégies** de routage (code dans `src/agents/supervisor.py`) :

1. **Routage déterministe** — Tant que les 3 agents n'ont pas tous reporté, le supervisor suit l'ordre fixe : `geopolitical_analyst` → `credit_evaluator` → `market_synthesizer`. Ce routage ne fait **aucun appel LLM** et ne consomme aucun token.

2. **Self-correction par LLM** — Une fois tous les agents passés, le supervisor évalue la qualité en lisant `risk_signals[]` (les synthèses, pas les messages bruts). S'il détecte une lacune, il peut re-router vers un agent. Sinon il envoie `FINISH`.

Le guard `iteration_count >= 10` empêche toute boucle infinie.

### 3. Le pattern ReAct — Comment un agent "réfléchit"

Chaque agent utilise le pattern **ReAct** (Reasoning + Acting). Concrètement, le LLM alterne entre :

1. **Thought** (Réflexion) — "Je dois trouver les données financières de NVIDIA"
2. **Action** (Outil) — Appelle `get_market_data("NVDA")`
3. **Observation** — Reçoit les données : prix, P/E, dette, etc.
4. **Thought** — "Le P/E est de 65, c'est élevé. Je dois aussi vérifier…"
5. **Action** — Appelle un autre outil
6. Répète jusqu'à avoir assez d'informations (max **6 itérations**)

Le code de cette boucle est dans `src/agents/nodes.py` → `_run_react_loop()`.

### 4. RAG — Retrieval-Augmented Generation (Hybrid)

**Problème** : Le LLM a une date de coupure d'entraînement. Il ne connaît pas les derniers rapports financiers et il peut "halluciner" (inventer des chiffres).

**Solution** : Le RAG permet au LLM de **chercher dans une base de documents** avant de répondre.

#### Approche hybride : Vector + BM25

Contrairement à un RAG classique (recherche vectorielle seule), ce système combine **deux méthodes** et les fusionne avec **Reciprocal Rank Fusion (RRF)** :

```text
Requête agent : "Apple supply chain risk China Taiwan"
    │
    ├──── Recherche sémantique (60%)          ├──── Recherche par mots-clés BM25 (40%)
    │     ChromaDB + all-MiniLM-L6-v2         │     Algorithme BM25 sur les mêmes docs
    │     Similarité cosinus                   │     Correspondance exacte des termes
    │     → Top-K résultats                    │     → Top-K résultats
    │                                          │
    └────────────────┬─────────────────────────┘
                     │
                     ▼
           Reciprocal Rank Fusion (k=60)
           Score = Σ weight × (1 / (k + rank))
                     │
                     ▼
           Top documents fusionnés et re-classés
           → Le LLM lit ces documents pour répondre
```

**Documents seed** : 6 PDFs dans `data/docs/` (WEF Global Risks 2026, Apollo Credit Outlook, etc.) sont indexés automatiquement au premier lancement.

Le code complet est dans `src/tools/rag_pipeline.py`.

### 5. Optimisations Token & Coût

Trois optimisations réduisent significativement les coûts :

| Optimisation | Gain estimé | Fichier |
| :--- | :--- | :--- |
| **Message Pruning** — Suppression des `ToolMessages` et `AIMessages` intermédiaires entre agents. Seules les synthèses nommées sont conservées. | ~40-50% tokens/run | `nodes.py` → `_prune_messages()` |
| **Supervisor léger** — Le supervisor évalue la qualité via `risk_signals[]` (~2.5K tokens) au lieu de l'historique brut complet (~50K tokens). | ~95% sur l'évaluation | `supervisor.py` → lectures de `risk_signals` |
| **Retry avec backoff** — Exponentiel avec jitter pour les rate limits Gemini (free tier). Évite les crashs et optimise le quota. | Fiabilité | `utils.py` → `retry_with_backoff()` |

### 6. Sources de données

| Source | Type | Fraîcheur | Fichier |
| :--- | :--- | :--- | :--- |
| **DuckDuckGo News** | Live | Actualités récentes | `src/tools/news_api.py` |
| **Yahoo Finance** | Live | Données marché temps réel | `src/tools/market_data.py` |
| **DuckDuckGo Web** | Live | Recherche web générale | `src/tools/news_api.py` |
| **ChromaDB RAG** | Statique | Documents seed (PDFs 2025-2026) | `src/tools/rag_pipeline.py` |

### 7. Interface Streamlit

L'interface web (`app.py`) offre :

- **Dashboard de configuration** — Sidebar avec templates de requêtes pré-définies (Apple, NVIDIA, Volkswagen, TotalEnergies, Deutsche Bank) ou requête custom
- **Pipeline visuel temps réel** — Barre de progression animée montrant l'état de chaque agent (Waiting → Running → Done)
- **Streaming de pensée** — Les actions des agents sont remontées en temps réel via `queue.Queue` partagé
- **Cards de métriques** — Score global, sous-scores par catégorie, notation crédit, avec code couleur (Low/Moderate/High/Critical)
- **Radar chart Plotly** — Visualisation des 4 sous-scores de risque (Géopolitique, Crédit, Marché, ESG)
- **Détection d'entité** — Identifie automatiquement si l'entité est cotée en bourse via `yfinance.Search` (badge Public/Privé)
- **Panel de sources** — Affichage des sources utilisées par catégorie (News, Market Data, RAG Documents)
- **Historique** — Accès aux rapports précédents depuis la sidebar
- **Export** — Téléchargement du rapport en Markdown

### 8. LangSmith — Observabilité

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

Le système track aussi les **tokens par agent** (input, output, cached) et calcule le coût estimé de chaque run directement dans le terminal et dans l'UI.

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

L'image Docker utilise `python:3.13-slim` et lance par défaut `python -m src.main --redis`.

---

## Project Structure

```text
RiskAnalysis/
├── app.py                    # Streamlit web interface (dashboard complet)
├── src/
│   ├── agents/
│   │   ├── prompts.py        # System prompts spécialisés (ReAct format)
│   │   ├── nodes.py          # Node functions + ReAct loop + token tracking
│   │   └── supervisor.py     # Routage déterministe + self-correction LLM
│   ├── tools/
│   │   ├── market_data.py    # Yahoo Finance (prix, ratios, bilan, historique)
│   │   ├── news_api.py       # DuckDuckGo News + Web search
│   │   └── rag_pipeline.py   # Hybrid RAG: ChromaDB vectors + BM25 + RRF
│   ├── state/
│   │   └── schema.py         # AgentState TypedDict (messages, risk_signals, etc.)
│   ├── utils.py              # Retry avec exponential backoff + jitter
│   ├── graph.py              # StateGraph builder + Redis/Memory checkpointing
│   └── main.py               # Async entrypoint + source extraction + cost calc
├── data/
│   ├── docs/                 # PDFs seed pour le RAG (WEF, Apollo, etc.)
│   └── chroma_db/            # ChromaDB persistence (auto-généré)
├── output/                   # Rapports générés (Markdown)
├── RiskAnalysis_Architecture.drawio  # Diagramme d'architecture (Draw.io)
├── glossaire.md              # Glossaire technique EN→FR
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                      # API keys (git-ignored)
```

## Agents

| Agent | Role | Tools | Prompt |
| :--- | :--- | :--- | :--- |
| **Supervisor** | Pipeline routing (déterministe puis self-correction LLM) | Structured JSON output | `SUPERVISOR_EVALUATION_PROMPT` |
| **Geopolitical Analyst** | Risques macro, géopolitiques, sanctions, supply chain | `search_geopolitical_news`, `search_web_general`, `search_corporate_disclosures` | `GEOPOLITICAL_SYSTEM_PROMPT` |
| **Credit Risk Evaluator** | Analyse crédit quantitative (Z-Score, ratios, notation) | `get_market_data`, `search_corporate_disclosures`, `search_web_general` | `CREDIT_SYSTEM_PROMPT` |
| **Market Synthesizer** | Rapport intégré final (CRO-level, score 0-100) | `search_corporate_disclosures`, `search_web_general` | `SYNTHESIZER_SYSTEM_PROMPT` |

## State Schema (`AgentState`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `messages` | `Annotated[Sequence[BaseMessage], add_messages]` | Messages accumulés (auto-merge LangGraph) |
| `next_agent` | `str` | Prochain agent à exécuter (décision du supervisor) |
| `current_company` | `str` | Entité en cours d'analyse |
| `risk_signals` | `Annotated[list[dict], operator.add]` | Synthèses intermédiaires par agent (auto-append) |
| `final_report` | `str` | Rapport de risque final |
| `iteration_count` | `int` | Compteur de sécurité anti-boucle infinie (max 10) |
| `token_usage` | `Annotated[list[dict], operator.add]` | Suivi des tokens par appel LLM |

## Output

The framework produces a structured **Integrated Risk Assessment Report** with:

- Overall Risk Score (0-100)
- Risk decomposition (Geopolitical, Credit, Market, ESG)
- Internal Credit Rating (AAA-D) with outlook
- Scenario analysis (Bull/Base/Bear with probabilities)
- Actionable recommendations
- Source citations

Reports are saved to `output/risk_report_YYYYMMDD_HHMMSS.md`.

---

**Stack**: Python 3.13 · LangGraph · Gemini 2.5 Flash · ChromaDB · BM25/RRF · Redis · Streamlit · Plotly · Docker · Asyncio
