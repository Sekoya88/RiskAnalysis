# RiskAnalysis — Guide Technique & Préparation Entretien

## 1. Vue d'ensemble du projet

**RiskAnalysis** est un système multi-agents d'évaluation des risques financiers. Il combine :
- Analyse géopolitique (contexte macro, sanctions, supply chain)
- Analyse de crédit (ratios financiers, notation, Altman Z-score)
- Synthèse marché (rapport de niveau board, scénarios)

**Stack principale :**
- Orchestration : **LangGraph** (state machine) + **LangChain**
- Backend : **FastAPI** + uvicorn (ASGI)
- LLM local : **Ollama** (qwen3.5, lfm2)
- LLM cloud : **Google Gemini 2.5 Flash**
- Embeddings : Ollama (`embeddinggemma`) ou HuggingFace (`all-MiniLM-L6-v2`)
- BDD : **PostgreSQL + pgvector** (prod) / SQLite (dev)
- Cache état : **Redis** (checkpoint LangGraph)
- Données marché : **yfinance** (Yahoo Finance)
- Recherche web : **DuckDuckGo** (ddgs)
- Validation : **Pydantic v2**

---

## 2. Architecture logicielle : Clean Architecture + DDD

Le projet adopte une **Clean Architecture** avec séparation stricte en couches :

```
src/
├── domain/              # Cœur métier pur (0 dépendance externe)
│   ├── models/          # Value objects : RiskReport, Source
│   ├── ports/           # Interfaces (protocoles Python) : LLMPort, VectorStorePort…
│   └── services/        # Logique métier pure : risk_scoring.py, report_builder.py
│
├── application/         # Orchestration LangGraph
│   ├── dto.py           # AgentState (TypedDict — état LangGraph)
│   ├── graph.py         # Construction du StateGraph
│   ├── supervisor.py    # Nœud superviseur (routage + auto-correction)
│   └── agents/          # Nœuds agents (geopolitical, credit, synthesizer)
│       └── base.py      # Boucle ReAct partagée
│
├── infrastructure/      # Implémentations concrètes (adapters)
│   ├── llm/             # OllamaAdapter, GeminiAdapter
│   ├── embeddings/      # OllamaEmbeddingAdapter, HuggingFaceAdapter
│   ├── vector_store/    # PgVectorStoreAdapter, ChromaAdapter
│   ├── data_sources/    # YahooFinanceAdapter, DuckDuckGoAdapter
│   ├── retrieval/       # HybridRetriever (vector + BM25 + RRF)
│   ├── persistence/     # PostgresRepository, SQLiteRepository, RedisCheckpointer
│   └── skills/          # Chargeur de SKILL.md (prompts système)
│
├── container.py         # Dependency Injection — composition root
├── api.py               # FastAPI : routes REST + WebSocket
└── main.py              # Point d'entrée CLI + exécuteur du graphe
```

**Règle clé :** le `domain/` ne connaît pas `infrastructure/`. Les dépendances sont injectées via `container.py` qui implémente les ports.

---

## 3. Architecture agentique : LangGraph StateGraph

### 3.1 Le graphe d'état

```
START
  │
  ▼
Supervisor ──────────────────────────────────────────────────┐
  │                                                          │
  ├─→ geopolitical_analyst (1er nœud)                        │
  │         │ ReAct loop (max 6 iter)                        │
  │         ▼                                                │
  ├─→ credit_evaluator (2e nœud)                             │
  │         │ ReAct loop (max 6 iter)                        │
  │         ▼                                                │
  ├─→ market_synthesizer (3e nœud)                           │
  │         │ ReAct loop (max 4 iter)                        │
  │         ▼                                                │
  └─→ Supervisor (évaluation finale)                         │
          │                                                  │
          ├─ Rapport insuffisant → re-route vers agent ──────┘
          │  (max 10 itérations globales)
          └─ Rapport OK → FINISH
```

### 3.2 AgentState (TypedDict partagé)

```python
class AgentState(TypedDict):
    messages: list[BaseMessage]       # Historique complet des messages
    risk_signals: list[dict]          # Analyses accumulées par agent
    next_agent: str                   # Décision de routage du superviseur
    iteration_count: int              # Garde-fou anti-boucle infinie
    final_report: str                 # Rapport Markdown final
    structured_report: RiskReport     # Rapport parsé (scores, rating…)
    token_usage: list[dict]           # Tracking coût par agent
```

### 3.3 Rôle de chaque agent

| Agent | Température | Max tokens | Outils |
|-------|------------|------------|--------|
| Supervisor | 0.0 | 512 | Aucun (routage pur) |
| Geopolitical Analyst | 0.2 | 4096 | search_geopolitical_news, search_web_general, search_corporate_disclosures |
| Credit Evaluator | 0.1 | 4096 | get_market_data, search_corporate_disclosures, search_web_general |
| Market Synthesizer | 0.15 | 8192 | search_corporate_disclosures, search_web_general |

### 3.4 Boucle ReAct (par agent)

```
Invoke LLM (avec outils liés via bind_tools)
  │
  ├─ LLM génère des tool_calls ?
  │     ├─ Oui → exécuter outils → ajouter ToolMessages → reboucler
  │     └─ Non → extraire texte final → retourner au superviseur
  │
  └─ Max iterations atteint → forcer extraction du texte
```

### 3.5 Prompts système : SKILL.md

Chaque agent charge son système prompt depuis `skills/<nom>/SKILL.md` :
```
skills/
├── supervisor/SKILL.md
├── geopolitical-analyst/SKILL.md
├── credit-evaluator/SKILL.md
└── market-synthesizer/SKILL.md
```
Format : frontmatter YAML + corps Markdown. Avantage : prompts versionnés dans git, modifiables sans toucher au code.

---

## 4. RAG Hybride (Retrieval-Augmented Generation)

### Pipeline de retrieval

```
Requête textuelle
      │
      ├─→ [1] Vector Search (pgvector)
      │         Embedding (Ollama/HuggingFace) → cosine similarity → top 20
      │
      ├─→ [2] BM25 Search (rank-bm25)
      │         Index en mémoire sur les chunks → top 20
      │
      └─→ [3] Reciprocal Rank Fusion (RRF, k=60)
                Fusion des scores des deux listes → tri unifié → top N
```

**RRF score** = `1/(k + rank_vector) + 1/(k + rank_bm25)`

Les documents sont les PDFs dans `data/docs/` (rapports WEF, Apollo, outlooks 2026). Ils sont ingérés via `just reseed-rag`.

---

## 5. Feedback RL (Reinforcement Learning)

Boucle d'amélioration continue des sources :

1. L'utilisateur note une source (`/api/feedback` : `is_helpful: true/false`)
2. Score sauvegardé en BDD (`feedback` table)
3. `compute_feedback_score = helpful_votes / total_votes`
4. `compute_rl_weight` = score de feedback + décroissance temporelle :
   - Article < 1 jour : +0.2
   - Article < 3 jours : +0.1
   - Article > 30 jours : -0.1
5. Lors de la prochaine analyse, les sources sont triées par `rl_weight` desc

---

## 6. API & Streaming

| Endpoint | Méthode | Rôle |
|----------|---------|------|
| `/api/analyze` | POST | Lancer une analyse multi-agents |
| `/api/feedback` | POST | Soumettre un feedback sur une source |
| `/api/reports` | GET | Historique des rapports (stub) |
| `/api/ws/stream` | WebSocket | Stream en temps réel des logs d'exécution |

**Body `/api/analyze` :**
```json
{
  "query": "Évalue le risque pour Apple Inc...",
  "use_redis": true,
  "model": "qwen3.5"
}
```

**Réponse :**
```json
{
  "status": "success",
  "thread_id": "uuid",
  "report": "...",
  "sources": { "news": [...], "market": [...], "rag": [...] },
  "token_usage": [...],
  "structured_report": { "entity": "Apple", "overall_score": 72, ... },
  "elapsed_seconds": 45.23
}
```

Le WebSocket broadcast les messages du middleware (start agent, tool call, token count) en temps réel via `AgentMiddleware`.

---

## 7. Persistance & Infrastructure

| Couche | Prod | Dev |
|--------|------|-----|
| Rapports & Feedback | PostgreSQL | SQLite (`data/risk_history.db`) |
| Vector Store (RAG) | pgvector (extension PG) | ChromaDB |
| Checkpointing LangGraph | Redis | MemorySaver (en mémoire) |
| Mémoire agents | FileMemoryAdapter (`data/agent_memory.md`) | — |

**docker-compose.yml** orchestre :
- `postgres` (pgvector/pgvector:pg17, port 5432)
- `redis` (redis-stack-server, port 6379)
- `api` (FastAPI, port 8000) — dépend des deux précédents

---

## 8. Flux complet d'une requête

```
1. POST /api/analyze
2. Initialisation DI container (LLM, embeddings, vector store, tools)
3. Création AgentState initial (messages=[HumanMessage])
4. Exécution du graphe LangGraph (stream_mode="values")
5. Supervisor → Geo Analyst (ReAct + tools) → Supervisor → Credit (ReAct) → Supervisor → Synthesizer (ReAct)
6. Supervisor évalue → FINISH ou re-route
7. Extraction sources depuis ToolMessages
8. Parsing RiskReport (regex sur le Markdown du synthesizer)
9. Sauvegarde BDD (rapport + news + token_usage)
10. Écriture fichier output/risk_report_YYYYMMDD.md
11. Retour JSON à l'API
```

---

## 9. Questions pièges d'entretien

### Architecture & Design Patterns

**Q : Pourquoi utiliser des Ports/Adapters (Hexagonal Architecture) ici ?**
> Pour découpler la logique métier (domaine) des frameworks externes. Si on veut passer de Chroma à pgvector, ou d'Ollama à Gemini, on implémente juste un nouvel adapter sans toucher au domaine. Ça rend aussi le code testable : en test, on mocke le port sans instancier une vraie BDD.

**Q : Quelle est la différence entre `src/agents/` et `src/application/agents/` ?**
> `src/agents/` est l'ancienne implémentation (legacy, conservée pour compatibilité). `src/application/agents/` est la version DDD propre. `src/graph.py` à la racine est un shim de compatibilité qui importe depuis `application`. C'est une migration en cours, pas un doublon intentionnel.

**Q : Pourquoi le Supervisor a température 0.0 ?**
> Le superviseur prend des décisions de routage déterministes. On ne veut aucune créativité, seulement la cohérence. Les agents analytiques ont des températures légèrement plus élevées pour produire des synthèses nuancées.

**Q : Comment LangGraph garantit-il qu'on ne boucle pas à l'infini ?**
> Double garde-fou : `iteration_count` dans l'état (max 10 global, vérifié dans la condition de routage), et `max_iterations` (max 6) dans la boucle ReAct de chaque agent. Le superviseur peut aussi forcer FINISH si iteration_count ≥ seuil.

---

### LLM & Agents

**Q : C'est quoi exactement la boucle ReAct ?**
> ReAct = Reasoning + Acting. Le LLM reçoit les outils via `bind_tools`. À chaque appel, il peut soit générer du texte (réponse finale), soit générer des `tool_calls` (JSON structuré décrivant l'outil à appeler et ses paramètres). On exécute les outils et on reinjecte les résultats comme `ToolMessage`. On répète jusqu'à plus de tool_calls ou max iterations.

**Q : Comment les outils sont-ils définis et transmis au LLM ?**
> Via `@tool` decorator de LangChain ou `BaseTool`. Le schéma Pydantic des arguments est converti en JSON Schema et transmis au LLM dans l'API (OpenAI tools format). Le LLM retourne des `tool_calls` avec le nom de l'outil et les arguments en JSON.

**Q : Quelle est la différence entre routing déterministe et routing LLM-based ?**
> Ici, le superviseur suit un pipeline A→B→C fixe (géo → crédit → synthèse). Le LLM du superviseur ne fait que valider et, en phase de self-correction, potentiellement re-router. Un routing purement LLM demanderait au modèle de choisir librement le prochain agent à chaque étape, ce qui est plus flexible mais moins prévisible et 60-80% plus coûteux en tokens.

**Q : Pourquoi le Market Synthesizer a max_tokens=8192 et les autres 4096 ?**
> Le synthétiseur doit intégrer les analyses des deux agents précédents (qui sont passées dans le state) plus générer un rapport complet. Il a besoin d'un contexte de sortie plus grand. Les autres agents produisent des analyses sectorielles plus ciblées.

**Q : Comment le state LangGraph est-il persisté entre deux appels ?**
> Via Redis avec `langgraph-checkpoint-redis`. Chaque thread a un `thread_id` unique. Le graphe peut être repris (`ainvoke` avec le même `thread_id`) depuis le dernier checkpoint. Sans Redis, `MemorySaver` garde l'état en mémoire (perdu au redémarrage).

---

### RAG & Retrieval

**Q : Pourquoi combiner vector search et BM25 ?**
> BM25 est excellent pour les correspondances de mots-clés exacts (noms propres, termes techniques, tickers boursiers). La recherche vectorielle capture la similarité sémantique. RRF (Reciprocal Rank Fusion) combine les deux classements sans nécessiter de normalisation des scores — il suffit du rang dans chaque liste.

**Q : Qu'est-ce que RRF et pourquoi k=60 ?**
> `score_rrf = 1/(k + rank)`. k=60 est la valeur empiriquement établie dans le papier original de RRF (Cormack 2009). Elle lisse les différences entre les hauts rangs (évite qu'un rang 1 écraserait trop le rang 2). En pratique, k=60 donne de bons résultats pour la plupart des corpus.

**Q : Où sont stockés les embeddings et comment sont-ils créés ?**
> Dans PostgreSQL via l'extension pgvector. Lors du seeding (`just reseed-rag`), les PDFs sont découpés en chunks, chaque chunk est transformé en vecteur flottant via le modèle d'embedding, puis stocké dans une table avec la colonne de type `vector(N)`. Les requêtes utilisent l'opérateur `<->` (distance cosinus).

---

### Infrastructure & Déploiement

**Q : Pourquoi utiliser Redis pour le checkpointing LangGraph plutôt que PostgreSQL ?**
> Redis est optimisé pour les opérations read/write rapides sur des données de session. Le checkpointing LangGraph écrit l'état complet à chaque nœud — ça peut représenter beaucoup d'écritures. PostgreSQL est utilisé pour la persistance longue durée des rapports. Les deux ont des rôles différents.

**Q : Que se passe-t-il si Redis n'est pas disponible au démarrage ?**
> Le code fallback sur `MemorySaver` (état en mémoire). L'analyse continue normalement mais l'état n'est pas persisté entre les redémarrages et on ne peut pas reprendre un thread interrompu.

**Q : Pourquoi CORS est configuré sur `["*"]` ?**
> C'est une configuration de développement. En production, il faudrait restreindre aux domaines autorisés (frontend). C'est d'ailleurs noté dans le code comme TODO. Laisser `["*"]` en prod expose l'API à des requêtes cross-origin de n'importe quelle origine.

**Q : Comment fonctionne le streaming WebSocket ?**
> `AgentMiddleware` intercepte les événements des nœuds (start, tool_call, done) et les publie dans une queue asyncio. L'endpoint WebSocket `/api/ws/stream` lit cette queue et pousse les messages JSON au client. C'est un pattern pub/sub léger sans broker externe.

---

### Optimisation & Coût

**Q : Comment le système optimise-t-il les coûts LLM ?**
> Plusieurs mécanismes : (1) routing déterministe évite de solliciter le LLM pour choisir le prochain agent à chaque step, (2) iteration guards empêchent les boucles coûteuses, (3) context caching Gemini pour les system prompts (si activé), (4) pruning des messages (seules les synthèses finales des agents précédents sont passées au suivant, pas les tool_calls bruts), (5) tracking précis input/output/cached tokens par agent.

**Q : Pourquoi tracked les tokens par agent plutôt qu'en global ?**
> Pour identifier quel agent est le plus coûteux et optimiser en priorité. Le synthesizer est généralement le plus cher (contexte long, sortie longue). Ça permet aussi de calculer un coût estimé par analyse et d'alerter si un agent consomme anormalement.

**Q : Comment le RL feedback améliore-t-il les analyses dans le temps ?**
> Le feedback utilisateur pondère le classement des sources lors de la prochaine analyse. Les sources notées utiles remontent dans les résultats de `search_geopolitical_news` et `search_web_general`. Avec suffisamment de feedback, le système apprend à privilegier les sources fiables pour un type de requête donné. C'est du bandit contextuel simplifié, pas du deep RL.

---

### Questions de design

**Q : Pourquoi les SKILL.md et pas les prompts directement dans le code ?**
> Séparation des responsabilités : les prompts sont des artifacts de produit qui évoluent souvent (wording, format de sortie, instructions). Les mettre en Markdown versionnés dans git permet de les modifier sans déploiement code, de les reviewer facilement en PR, et de les partager avec des non-développeurs.

**Q : Comment ajouteriez-vous un 4e agent (ex: ESG analyst) ?**
> 1. Créer `skills/esg-analyst/SKILL.md`, 2. Créer `src/application/agents/esg.py` héritant de `base.py`, 3. Ajouter le nœud au graphe dans `application/graph.py`, 4. Mettre à jour le superviseur pour inclure `esg_analyst` dans le pipeline, 5. Ajouter `esg_score` dans `AgentState` et `RiskReport`. La Clean Architecture limite les changements à ces 5 fichiers.

**Q : Quelles sont les limites actuelles du système ?**
> - `/api/reports` (historique) n'est pas implémenté (stub)
> - CORS ouvert (`["*"]`) non sécurisé pour la prod
> - Pas de rate limiting sur l'API
> - Le RL est simplifié (pas de contextualisation par type d'entreprise/secteur)
> - BM25 index reconstruit en mémoire à chaque requête (pas de persistance)
> - Pas d'authentification/autorisation sur les endpoints

**Q : Pourquoi avoir un `container.py` dédié ?**
> C'est le **composition root** — le seul endroit où les dépendances concrètes sont assemblées. Ça centralise la configuration et facilite les tests (on peut swapper les adapters sans modifier les agents). Alternative à des frameworks DI comme `dependency-injector`.

---

## 10. Observabilité : Langfuse (intégré)

### 10.1 Ce qui est tracé automatiquement

Langfuse capture **chaque appel LLM, chaque tool call et chaque nœud LangGraph** via le mécanisme de callbacks LangChain. Un `CallbackHandler` est créé **par requête** (pas de singleton global) pour isoler les traces :

```text
Requête /api/analyze
  └── Trace Langfuse (session_id = thread_id)
       ├── Span: supervisor_node → routing decision
       ├── Span: geopolitical_analyst
       │    ├── LLM call (qwen3.5 / gemini-2.5-flash)
       │    ├── Tool: search_geopolitical_news
       │    └── Tool: search_corporate_disclosures
       ├── Span: credit_evaluator
       │    ├── LLM call
       │    └── Tool: get_market_data
       └── Span: market_synthesizer
            └── LLM call (rapport final)
```

### 10.2 Configuration

**Démarrer le service self-hosted :**

```bash
docker compose up langfuse -d
# UI disponible sur http://localhost:3001
```

Créer un projet → récupérer `Public Key` + `Secret Key` → les mettre dans `.env` :

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3001
```

Si les clés ne sont pas configurées, le traçage est **silencieusement désactivé** (pas de crash).

### 10.3 Ce qu'on voit dans l'UI

| Vue Langfuse | Utilité |
| --- | --- |
| **Traces** | Chaque run complet avec tous les spans |
| **Latency breakdown** | Quel agent prend le plus de temps |
| **Token usage** | Coût par agent, par modèle |
| **Scores** | Si on ajoute des évaluations manuelles/LLM-as-judge |
| **Sessions** | Grouper plusieurs runs pour la même query |

---

## 11. Gaps d'implémentation vs spec technique

### Point 3 — Human-in-the-loop : ❌ NON IMPLÉMENTÉ

La spec mentionne `human-in-the-loop` comme fallback. **Ce n'est pas implémenté.** Voici ce qu'il faudrait ajouter :

**Ce que LangGraph supporte :**

```python
# Dans build_graph() — ajouter des interrupt points
workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["market_synthesizer"],  # pause avant la synthèse
)
```

**Ce qu'il faudrait ajouter à l'API :**

```python
# Nouvel endpoint pour reprendre après approbation humaine
@app.post("/api/resume/{thread_id}")
async def resume(thread_id: str, approved: bool):
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}
    if approved:
        await graph.aupdate_state(config, {"approved": True})
        await graph.ainvoke(None, config=config)  # reprend depuis le checkpoint
```

**Pourquoi ce n'est pas critique ici :** le pipeline est déterministe (routing superviseur → pipeline fixe) et les agents ne prennent pas de décisions irréversibles. Le HITL serait utile pour valider le rapport final avant envoi dans un système de production.

### Point 4 — Observabilité Langfuse : ✅ IMPLÉMENTÉ

Langfuse est maintenant intégré avec :

- `CallbackHandler` par requête dans `/api/analyze`
- Service Docker self-hosted (`docker compose up langfuse`)
- Flush propre au shutdown FastAPI (`shutdown_langfuse()`)
- Fallback silencieux si non configuré

---

## 12. Mémo architecture en une phrase

> RiskAnalysis est un **pipeline LangGraph déterministe** où trois agents ReAct spécialisés (géopolitique → crédit → synthèse) enrichissent progressivement un **état partagé**, sous supervision d'un orchestrateur auto-correcteur, en utilisant un **RAG hybride** (vector + BM25) sur des PDFs financiers et des données marché en temps réel, avec un **feedback loop RL** pour améliorer le classement des sources.
