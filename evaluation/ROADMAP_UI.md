# Roadmap — affichage évaluation dans `riskanalysis-ui`

## Phase 1 — Lecture seule
- Endpoint backend `GET /api/eval/last` ou réutiliser la payload existante : étendre `POST /api/analyze` avec `include_trace: bool` (optionnel) qui retourne `eval` (JSON compact : latence, steps, tool_count, token totals) **sans** refaire de calcul lourd côté client.
- Panneau « Run metrics » dans `ReportView` ou sidebar : latence, étapes graphe, # tools, coût estimé.

## Phase 2 — Lancement d’évals
- `POST /api/eval/run` avec body `{ "query": "...", "ground_truth": { ... } }` qui appelle `evaluate_agent_run` et renvoie `SingleRunReport`.
- Page `/eval` réservée dev : liste des runs, téléchargement JSON.

## Phase 3 — Dataset
- Fichiers `evaluation/datasets/*.yaml` (query + `GroundTruth`) versionnés ; script `python -m evaluation.batch_run` qui agrège via `aggregate_reports`.

## Phase 4 — Dashboards
- Graphiques tendance (latence, F1 retrieval) stockés dans Postgres ou fichiers `output/eval_history/`.

Non-bloquant : le front actuel continue d’appeler `POST /api/analyze` sans changement.
