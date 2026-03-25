# RiskAnalysis — Justfile
# Usage: just <recipe>

# One-time: strip "Made-with: Cursor" etc. from commits (uses .githooks/commit-msg)
git-hooks:
    git config core.hooksPath .githooks

OLLAMA_MODEL := env("OLLAMA_MODEL", "qwen3.5")

# ── Dev shortcuts ─────────────────────────────────────────────────
# `just backend` → Postgres + Redis + Langfuse (Docker) + uvicorn local (venv).
# `just db-langfuse` → crée la base `langfuse` si besoin (premier lancement Langfuse).

# Start everything (Postgres + Redis + pull models + API)
start: services pull-all build
    docker compose up api

# Start infrastructure services (PostgreSQL + Redis)
services:
    docker compose up postgres redis -d

# Postgres + Redis + Langfuse UI (http://localhost:3001) — sans l’API Python
backend-deps:
    docker compose up postgres redis langfuse -d
    @echo "Postgres host port: ${POSTGRES_PORT_PUBLISH:-15432}  Langfuse: http://localhost:3001"
    @echo "Beekeeper: docs/BEEKEEPER.md"

# Crée la base `langfuse` dans le conteneur (ignore l’erreur si elle existe déjà)
db-langfuse:
    docker compose exec -T postgres psql -U risk -d postgres -c "CREATE DATABASE langfuse;" || true

# Stack locale complète : deps Docker + checkpoint PPO si torch (just ppo-ensure) + API
backend: backend-deps
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -x venv/bin/uvicorn ]]; then
        echo "Crée le venv: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
        exit 1
    fi
    if ./venv/bin/python -c "import torch" 2>/dev/null; then
        ./venv/bin/python -m src.rl.train_ppo_sources --skip-if-exists --steps 800 --save data/ppo_source_policy.pt
    else
        echo "PPO: torch absent — pip install -r requirements-rl.txt pour générer data/ppo_source_policy.pt au lancement"
    fi
    exec ./venv/bin/uvicorn src.api:app --reload --host 127.0.0.1 --port 8000

# Start Redis only
redis:
    docker compose up redis -d

# Start PostgreSQL only
postgres:
    docker compose up postgres -d

# Pull all supported models
pull-all:
    ollama pull qwen3.5
    ollama pull lfm2

# Pull a specific model
pull model="qwen3.5":
    ollama pull {{model}}

# Build the API image
build:
    docker compose build api

# Start FastAPI server (local dev, no Docker for app)
dev: services
    uvicorn src.api:app --reload

# Alias: même chose que `backend-deps` (nom explicite)
langfuse-up:
    docker compose up postgres redis langfuse -d

# Re-ingest RAG docs from data/docs/ into pgvector (requires DATABASE_URL + Ollama embeddinggemma)
reseed-rag:
    python3 -c "from dotenv import load_dotenv; load_dotenv(); from src.container import reseed_rag_documents; n = reseed_rag_documents(); print(f'Reseeded: {n} chunks')"

# Run CLI mode
cli *ARGS: redis
    OLLAMA_MODEL={{OLLAMA_MODEL}} python3 -m src.main {{ARGS}}

# Stop everything
stop:
    docker compose down

# Clean everything (volumes included)
clean:
    docker compose down -v

# Show logs
logs:
    docker compose logs -f api

# Simulated evaluation JSON (no LLM)
eval-sim:
    python3 -m evaluation.examples.sim_full_run

# Unit tests for evaluation.metrics
eval-test:
    pytest evaluation/tests/ -v

# Train PPO source-ranking policy (needs: pip install -r requirements-rl.txt)
ppo-train:
    python3 -m src.rl.train_ppo_sources --steps 2000 --save data/ppo_source_policy.pt

# Create default checkpoint once if missing (for PPO on by default)
ppo-ensure:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -x venv/bin/python ]]; then
        echo "Need venv: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt -r requirements-rl.txt"
        exit 1
    fi
    ./venv/bin/python -m src.rl.train_ppo_sources --skip-if-exists --steps 800 --save data/ppo_source_policy.pt
