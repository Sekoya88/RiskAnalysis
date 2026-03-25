FROM python:3.13-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt requirements-rl.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Optional PPO (torch): docker build --build-arg INSTALL_PPO=1 .
ARG INSTALL_PPO=0
RUN if [ "$INSTALL_PPO" = "1" ]; then pip install --no-cache-dir -r requirements-rl.txt; fi

# Application code
COPY . .

# Create output directory
RUN mkdir -p /app/output /app/data

# Environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
