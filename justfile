# RiskAnalysis — Justfile
# Usage: just <recipe>

OLLAMA_MODEL := env("OLLAMA_MODEL", "qwen3.5")

# Start everything (Postgres + Redis + pull models + App)
start: services pull-all build
    docker compose up app

# Start infrastructure services (PostgreSQL + Redis)
services:
    docker compose up postgres redis -d

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

# Build the app image
build:
    docker compose build app

# Start Streamlit UI (local dev, no Docker for app)
dev: services pull-all
    python3 -m streamlit run app.py

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
    docker compose logs -f app
