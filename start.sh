#!/bin/bash
set -e

MODEL=${OLLAMA_MODEL:-llama3}

echo "► Ollama başlatılıyor..."
ollama serve &
OLLAMA_PID=$!

# Ollama hazır olana kadar bekle
echo "► Ollama hazır bekleniyor..."
until curl -sf http://localhost:11434/api/tags > /dev/null; do
  sleep 1
done

echo "► Model indiriliyor: $MODEL"
ollama pull $MODEL

echo "► RunPod handler başlatılıyor..."
python handler.py
