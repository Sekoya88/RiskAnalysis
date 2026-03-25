# 📊 Métriques & Implémentation RLHF (Reinforcement Learning from Human Feedback)

L'architecture `RiskAnalysis` intègre un système de métriques pour évaluer les risques et un mécanisme de boucle de rétroaction (RLHF) pour améliorer la qualité des sources sur lesquelles les agents IA se basent.

> **PPO** : actor–critic discret (`src/rl/`), entraînable sur les votes `feedback` (`just ppo-ensure` / `just ppo-train`, `requirements-rl.txt`). Par défaut le backend charge **`data/ppo_source_policy.pt`** s’il existe ; **`PPO_DISABLED=1`** coupe le chargement ; **`PPO_SOURCE_POLICY_PATH`** surcharge le fichier. **Pas de fine-tuning du LLM** — seulement un delta sur le score des sources. Sans fichier `.pt`, **votes URL** + **`compute_rl_weight`** seuls.

Voici comment tout est calculé et implémenté sous le capot.

---

## 1. Les Métriques Utilisées

### A. Scores de Risque (Risk Scores)
Les agents génèrent et quantifient le risque d'une entité (ex: Apple Inc.) sur une échelle de **0 à 100**. Ces scores sont extraits du rapport final et persistés en base de données (`reports`).
*   **Overall Score** (Score Global)
*   **Geopolitical Score** (Score Géopolitique)
*   **Credit Score** (Score de Crédit)
*   **Market Score** (Score de Marché)
*   **ESG Score** (Environnement, Social, Gouvernance)

### B. Métriques d'Évaluation des Sources (RLHF)
Chaque source d'information (généralement une URL d'article d'actualité) possède une métrique de confiance dynamique :
*   **Base Feedback Score** : Ratio d'utilité voté par les humains (de 0.0 à 1.0).
*   **Time Decay Modifier** : Modificateur temporel de fraîcheur de l'information (+0.2, +0.1, -0.1).
*   **Final RL Weight** (Score Final) : La combinaison des deux, servant au tri.

### C. Télémétrie IA
*   **Token Usage** : Consommation de tokens (in/out) tracée à chaque étape du graphe LangGraph.
*   **Elapsed Time** : Temps d'exécution de l'analyse (calculé dans l'API et affiché sur le front).

---

## 2. Implémentation du RLHF (Comment ça marche ?)

Le système RLHF permet au framework d'apprendre au fil du temps quelles sources d'information (news) sont les plus pertinentes, en fonction des votes utilisateurs.

### Étape 1 : Collecte du Feedback Utilisateur
1. Lors de l'affichage d'un rapport sur l'interface (Next.js), les sources utilisées sont listées.
2. L'utilisateur peut marquer une source comme "Utile" (`is_helpful=true`) ou "Inutile" (`is_helpful=false`).
3. Le Front appelle la route REST `POST /api/feedback`.
4. Le Backend enregistre ce vote dans la table PostgreSQL `feedback` (liant `report_id`, `news_url`, `is_helpful` et `created_at`).

### Étape 2 : Calcul du Score de Base (Historique)
Lorsqu'une nouvelle analyse est lancée, l'agent cherche des news. Pour chaque URL trouvée, le système interroge la base de données via `get_source_feedback_score(url)`.

La logique métier (`src/domain/services/risk_scoring.py`) calcule un ratio :
*   **Neutre par défaut** : Si 0 vote, le score est `0.5`.
*   **Pénalité immédiate** : Si 1 seul vote et qu'il est négatif, le score tombe à `0.4`.
*   **Ratio global** : Sinon, `Nombre de votes positifs / Nombre total de votes` (ex: 8 utiles / 10 total = `0.8`).

### Étape 3 : Application du "Time Decay" (Pondération temporelle)
L'information financière/géopolitique périme vite. Le système applique un modificateur (`compute_rl_weight`) sur le Base Score en fonction de la date de l'article :
*   **≤ 1 jour** : `+ 0.2` (Bonus de fraîcheur extrême)
*   **≤ 3 jours** : `+ 0.1` (Bonus d'actualité récente)
*   **> 30 jours** : `- 0.1` (Pénalité d'information obsolète)

*Exemple : Un article très apprécié (Base Score = 0.9) mais vieux de 2 mois verra son poids ajusté à 0.8. Un article neutre (0.5) sorti il y a 2 heures grimpera à 0.7.*

### Étape 4 : Tri et Filtrage (Impact direct sur l'IA)
C'est ici que l'apprentissage prend tout son sens (`src/main.py`, ligne ~243) :
1. Une fois tous les articles scorés par l'algorithme RLHF, la liste est **triée par ordre décroissant**.
2. Le système tronque la liste pour ne garder que le **Top 10** des sources.
3. **Résultat** : Seules les sources les plus fiables (historiquement) et les plus récentes sont injectées dans le contexte du prompt de l'agent `Market Synthesizer`.
4. Les sites de "fake news" ou inutiles, systématiquement downvotés, finissent par avoir un score trop bas pour atteindre le Top 10 et sont ignorés par le système.

## Résumé du Cycle de Vie
`Search DuckDuckGo` ➔ `Récupération URLs` ➔ `SQL: Fetch Votes` ➔ `Ratio Utilité + Fraîcheur` ➔ `Tri (Top 10)` ➔ `Prompt Agent IA` ➔ `Génération Rapport` ➔ `Vote Utilisateur` ➔ `Boucle bouclée`.

---

## 3. Comment cela influence-t-il le LLM et les futures requêtes ?

C'est la question clé. **Le LLM lui-même (ses poids neuronaux) n'est absolument pas modifié.** Il n'y a pas de *fine-tuning* du modèle Qwen ou Gemini.

C'est ce qu'on appelle du **Contextual RLHF** (ou Agentic/RAG RLHF). Le LLM ne "sait" pas qu'il y a des métriques, il réagit uniquement au **contexte qu'on lui injecte dans son prompt**.

### La Mécanique (Garbage In, Garbage Out) :
L'intelligence de ce système ne réside pas dans le LLM, mais dans le **middleware (le code Python)** qui prépare les données *avant* de les donner au LLM.

1. **L'Influence sur le Contexte :**
   Si l'utilisateur A downvote un article de "fake-news-blog.com" (`is_helpful = false`), le score de cette URL (ou de ce domaine si on étend la logique) chute drastiquement en base de données.

2. **La Prochaine Requête (Utilisateur B) :**
   Le lendemain, l'utilisateur B pose une question similaire. L'agent de recherche (qui utilise DuckDuckGo) va bêtement remonter 30 articles, dont celui de "fake-news-blog.com" car les mots-clés matchent.
   
3. **Le Filtrage (La Magie du RLHF) :**
   Le backend intercepte ces 30 articles. Il interroge Postgres. Il voit que "fake-news-blog.com" a un score RLHF de `0.1` (très mauvais). Il voit que "reuters.com" a un score de `0.9` (grâce aux upvotes passés).
   Le backend trie la liste et **coupe au Top 10**. "fake-news-blog.com" est supprimé de la liste.

4. **Le Prompt Final du LLM :**
   Le `Market Synthesizer` (le LLM) reçoit finalement son prompt contenant uniquement les 10 meilleurs articles. **Le LLM ne verra jamais la fake news.**

### Conclusion sur l'influence :
Les réponses influencent les futures requêtes non pas en rendant le LLM "plus intelligent", mais **en lui fournissant une nourriture (un contexte) de plus en plus pure et vérifiée par les humains au fil du temps.** Le LLM génère de meilleurs rapports parce qu'on lui donne de meilleures sources.

---

## Module `evaluation/` (mesures sur le workflow agentique)

Un package Python à la racine du repo trace chaque exécution via le callback optionnel `trace_sink` sur `run_analysis` : latence, étapes du graphe, outils, tokens, P/R/F1 sur les URLs récupérées (vérité terrain optionnelle), proxy de fidélité au texte, coût USD estimé, score de robustesse si fallback Redis→mémoire. **Pas de fine-tuning LLM** ; le **PPO** (`src/rl/`) ajuste les scores de sources quand un checkpoint est présent et non désactivé (`PPO_DISABLED`).

Documentation : `evaluation/ROADMAP_UI.md` (intégration front). Commandes : `just eval-sim`, `just eval-test`.

### Ground truth optionnel (API + UI)

`POST /api/analyze` accepte des champs optionnels `metrics_*` (URLs news, clés RAG, faits de référence, séquence d’outils attendue, tâche complétée). Quand au moins l’un est renseigné, le backend calcule P/R/F1 (news et éventuellement RAG), faithfulness / hallucination proxy, précision d’ordre d’outils, etc., et les renvoie dans `run_metrics`. Le front (`riskanalysis-ui`) expose un panneau repliable pour les saisir.

### Mémo entre runs / même question

Deux mécanismes distincts : (1) **feedback URL** en base → toute analyse ultérieure qui **récupère à nouveau** ces URLs est réordonnancée (top‑k) ; ce n’est **pas** une mémoire « même prompt = même réponse ». (2) **PPO** sur les scores de sources si un `.pt` est présent (défaut `data/ppo_source_policy.pt`, désactivable) ; **jamais** de fine-tuning du LLM.