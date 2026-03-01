#!/bin/bash
set -e

# Default to Qwen 2.5 32B for high technical precision (128k context)
export OLLAMA_MODEL=${OLLAMA_MODEL:-"qwen2.5:32b"}
MODEL=$OLLAMA_MODEL

echo "► Starting PostgreSQL..."
# Ensure PostgreSQL service starts
service postgresql start

echo "► Configuring database..."
# Set Postgres password (required for Python app connection)
export PGPASSWORD=${DB_PASSWORD:-"postgres"}
su - postgres -c "psql -c \"ALTER USER postgres WITH PASSWORD '$PGPASSWORD';\""

# Create the rfq_db database and add required extensions
su - postgres -c "psql -c 'CREATE DATABASE rfq_db;'" || echo "Database may already exist."
su - postgres -c "psql -d rfq_db -c 'CREATE EXTENSION IF NOT EXISTS vector;'"
su - postgres -c "psql -d rfq_db -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm;'"

echo "► Checking Ollama status..."
if curl -sf http://localhost:11434/api/tags > /dev/null; then
  echo "► Ollama is already running."
else
  echo "► Starting Ollama..."
  ollama serve &
  # Wait for Ollama server to be ready
  echo "► Waiting for Ollama API..."
  until curl -sf http://localhost:11434/api/tags > /dev/null; do
    sleep 2
  done
fi

# Wait for model to be ready (especially if pre-bake failed or is loading)
echo "► Waiting for $MODEL model to be ready..."
until ollama list | grep -q "$MODEL"; do
  echo "  ... model not in list yet, waiting (may need pull) ..."
  ollama pull $MODEL
  sleep 5
done

# Short additional wait for model to load into VRAM (optional but healthy)
sleep 2
echo "► $MODEL ready!"

# Embedding model (for RAG and Hybrid Search)
echo "► Checking nomic-embed-text embedding model..."
ollama pull nomic-embed-text
echo "► nomic-embed-text ready!"

# Models are now pre-baked in the image, no need to download again
# echo "► Model indiriliyor: $MODEL"
# ollama pull $MODEL

echo "► Checking startup mode..."
if [ "$RUNPOD_SERVERLESS" = "true" ]; then
  echo "► Mode: RunPod Serverless"
  echo "► Starting RunPod handler..."
  python handler.py
else
  echo "► Mode: Standalone Pod (FastAPI Backend)"
  echo "► Starting FastAPI server..."
  
  # Kill old processes to prevent port conflicts
  pkill -f uvicorn || true
  
  # Make port configurable (Default 8080)
  PORT=${PORT:-8080}
  echo "► API port: $PORT"
  
  # Start the FastAPI application
  # --proxy-headers and --forwarded-allow-ips '*' are important for running behind RunPod proxy.
  uvicorn api:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'
fi
