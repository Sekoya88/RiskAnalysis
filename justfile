# RiskAnalysis — Justfile
# Usage: just <recipe>

OLLAMA_MODEL := env("OLLAMA_MODEL", "qwen3.5")

# Start everything (Redis + pull models + App)
start: redis pull-all build
    docker compose up app

# Start Redis only
redis:
    docker compose up redis -d

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
dev: redis pull-all
    streamlit run app.py

# Run CLI mode
cli *ARGS: redis
    OLLAMA_MODEL={{OLLAMA_MODEL}} python -m src.main {{ARGS}}

# Stop everything
stop:
    docker compose down

# Clean everything (volumes included)
clean:
    docker compose down -v

# Show logs
logs:
    docker compose logs -f app
