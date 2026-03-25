# Bonnes pratiques — Systèmes Agentiques

Guide de conception pour des pipelines multi-agents **rentables**, **rigoureux** et **réutilisables**. Applicable à tout domaine : risk, supply chain, finance, RH, production, etc.

---

## 1. Architecture

### 1.1 Clean Architecture (DDD)
- **Principe** : Séparer le domaine (modèles, règles), l'application (agents, graphe), l'infrastructure (Redis, ChromaDB, SQLite, APIs) et l'injection de dépendances (Container).
- **Pourquoi** : Rend le système multi-agents testable, évolutif et indépendant des LLMs ou bases de données sous-jacentes.

### 1.2 Orchestration déterministe d’abord
- **Principe** : Un superviseur déterministe dirige le flux. Le LLM n’est utilisé pour le routage que si nécessaire (auto-correction, cas ambigus).
- **Pourquoi** : Réduction massive des appels LLM inutiles.
- **Pattern** : Pipeline fixe (A → B → C) tant que tous les agents n’ont pas reporté ; ensuite, évaluation légère par LLM (sur un résumé condensé, pas sur 50K tokens).

### 1.3 Granularité des agents
- Un agent = une responsabilité claire.
- Limiter les agents à 3–5 spécialités pour garder une architecture lisible.
- Éviter les agents “fourre-tout” qui mélangent plusieurs missions.

### 1.3 Réduction de contexte
- Ne jamais renvoyer à un agent toute l’historique brut (messages + tool calls).
- Pruner les messages intermédiaires, garder uniquement les synthèses finales.
- Objectif : ~2–3K tokens pour la phase de supervision, pas 50K+.

---

## 2. Gestion des coûts

### 2.1 Choix du modèle selon la tâche
| Tâche | Modèle recommandé | Raison |
|-------|-------------------|--------|
| Routage / classification | Petit (Flash, Haiku) ou local | Peu de raisonnement, coût minimal |
| Analyse spécialisée | Moyen (Sonnet, Claude) ou local (8–24B) | Bon compromis qualité/coût |
| Synthèse finale | Plus puissant si budget | Impact direct sur la qualité du livrable |

### 2.2 Boucles ReAct limitées
- Borner les itérations (ex. 4–6 max par agent).
- Éviter les boucles infinies ou les appels LLM redondants.

### 2.3 Backoff et retry
- Implémenter un retry avec backoff exponentiel et jitter sur les appels API.
- Gérer explicitement les erreurs 429 / rate limit.

### 2.4 Caching
- Utiliser le cache de contexte quand le provider le supporte (Gemini, Claude).
- Réduit fortement le coût des tokens répétés.

---

## 3. Rigueur et fiabilité

### 3.1 Typage strict des entrées/sorties
- **Pydantic** (ou équivalent) pour les schémas des tools.
- Validation des arguments avant exécution.
- Formats de sortie prévisibles (JSON, objets typés).

### 3.2 Guardrails contre les boucles
- Compteur d’itérations max (ex. 10 invocations totales).
- Fallback déterministe (ex. FINISH) si le superviseur échoue.

### 3.3 Skills externalisés (pas de prompts en dur)
- Stocker les prompts dans des fichiers Markdown/YAML.
- Un fichier par agent (`skills/agent-name/SKILL.md`).
- Permet d’itérer sans modifier le code.

### 3.4 Logging structuré
- Un logger unique (ex. Loguru) pour tout le pipeline.
- Logs par étape : agent, tokens consommés, erreurs.
- Facilite le debug et l’audit.

---

## 4. Persistance et reproductibilité

### 4.1 Checkpointing
- Persister l’état du graphe (Redis, DB) pour les runs longs.
- Permet de reprendre après un crash ou une pause.

### 4.2 Traçabilité des sources et Résolution d'Entités
- **Enrichissement** : Résoudre les entités (ex: via `yfinance`) avant l'analyse pour adapter le comportement (entreprise publique vs privée).
- **Provenance** : Conserver la provenance exacte des données (news, market, RAG) et l'exposer dans le livrable final.

### 4.3 Feedback loop (RL simple) & Time Decay
- **Principe** : Stocker les votes utilisateur (utile / inutile) par source dans une base (ex: SQLite).
- **Pondération** : Calculer un score de confiance (ML Confidence) pour pondérer les sources à la prochaine exécution.
- **Time Decay** : Ajouter des bonus aux sources ultra-récentes (HOT < 24h, RECENT < 72h) pour prioriser la fraîcheur de l'information.

### 4.4 Agent Memory (Contexte Persistant)
- Maintenir un fichier persistant (ex: `data/agent_memory.md`) mis à jour automatiquement à chaque run pour offrir aux agents une mémoire cross-session des analyses passées.

---

## 5. Outils et intégrations

### 5.1 Tools avec schémas explicites
- Chaque tool a un `args_schema` Pydantic.
- Le LLM génère des arguments conformes au schéma.
- Évite les erreurs de parsing et les appels invalides.

### 5.2 RAG hybride
- Combiner recherche sémantique (vectors) et lexicale (BM25).
- Fusionner avec Reciprocal Rank Fusion (RRF).
- Améliore recall et précision par rapport à une seule méthode.

### 5.3 API externes
- Timeout et retry sur les appels externes.
- Ne pas exposer de secrets dans les logs.

---

## 6. Interface utilisateur

### 6.1 Feedback visible
- Confirmation immédiate quand l’utilisateur vote (ex. toast, badge).
- Limiter l’affichage des sources (ex. 10 max) pour ne pas surcharger.

### 6.2 Interface Temps Réel & Asynchronisme
- **Pattern** : Coupler `asyncio` pour l'exécution du graphe avec du `threading` et une `queue.Queue`.
- **Pourquoi** : Permet d'afficher les logs des agents et la progression du pipeline en temps réel dans l'UI (ex: Streamlit) sans bloquer la boucle d'événements principale.
- **Visuels** : Utiliser des graphiques interactifs (ex: Radar charts Plotly) pour décomposer visuellement les scores générés par les agents.

### 6.3 Coût estimé
- Afficher tokens in/out et coût estimé par run.
- Aide à piloter le budget et à détecter les dérives.

---

## 7. Déploiement et opération

### 7.1 Variables d’environnement
- Centraliser la config (modèle, API keys, Redis URL).
- Fichier `.env.example` sans valeurs sensibles.

### 7.2 Switch rapide de provider
- Support Ollama (local) + API (Gemini, Claude, etc.) via une seule variable.
- Choix dans l’UI ou dans la config, pas dans le code.

### 7.3 Observabilité (Tracing)
- Intégrer une solution de tracing complète (ex: LangSmith).
- Tracer chaque appel LLM, l'utilisation des tokens (input, output, cached), la latence, et les invocations de tools pour un debug end-to-end.

### 7.4 Health checks
- Endpoint ou script pour vérifier Redis, DB, ChromaDB.
- Arrêt propre si une dépendance critique est indisponible.

---

## 8. Checklist avant mise en production

- [ ] Architecture DDD (Domain, App, Infra) respectée
- [ ] Pipeline déterministe prioritaire, LLM en complément
- [ ] Limites d’itérations et guardrails anti-boucle
- [ ] Typage Pydantic sur tous les tools
- [ ] Logging structuré et observabilité (LangSmith)
- [ ] Persistance (Redis/DB) et Agent Memory pour les runs longs
- [ ] Feedback loop (votes) + time decay sur les sources
- [ ] Résolution d'entités en amont du pipeline
- [ ] UI asynchrone avec streaming des logs via Queue
- [ ] Retry + backoff sur les appels API
- [ ] Coût estimé visible par run
- [ ] Secrets en variables d’environnement, pas en dur
- [ ] Documentation (README) à jour avec les deux modes (local / API)

---

## 9. Références rapides

| Composant | Techno recommandée |
|-----------|--------------------|
| Orchestration | LangGraph |
| LLM local | Ollama |
| LLM cloud | Gemini, Claude, OpenAI |
| Vector DB | ChromaDB, pgvector |
| État | Redis (checkpoint), SQLite (feedback) |
| Validation | Pydantic |
| Logging | Loguru |
| UI | Streamlit, Gradio |

---

*Document générique — adaptable à tout pipeline agentique (risk, finance, supply chain, RH, etc.).*
