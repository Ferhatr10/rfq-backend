#!/bin/bash
set -e

MODEL=${OLLAMA_MODEL:-llama3}

echo "► Ollama başlatılıyor..."
ollama serve &
OLLAMA_PID=$!

# Ollama sunucusunun hazır olmasını bekle
echo "► Ollama API bekleniyor..."
until curl -sf http://localhost:11434/api/tags > /dev/null; do
  sleep 2
done

# Modelin hazır olmasını bekle (özellikle pre-bake başarısız olduysa veya yükleniyorsa)
echo "► $MODEL modelinin hazır olması bekleniyor..."
until ollama list | grep -q "$MODEL"; do
  echo "  ... model henüz listede yok, bekleniyor (pull gerekebilir) ..."
  ollama pull $MODEL
  sleep 5
done

# Modelin VRAM'e yüklenebilmesi için ek kısa bir bekleme (opsiyonel ama sağlıklı)
sleep 2
echo "► $MODEL hazır!"

# Modeller artık imajın içinde (pre-baked), tekrar indirmeye gerek yok
# echo "► Model indiriliyor: $MODEL"
# ollama pull $MODEL

echo "► Başlatma modu kontrol ediliyor..."
if [ "$RUNPOD_SERVERLESS" = "true" ]; then
  echo "► Mod: RunPod Serverless"
  echo "► RunPod handler başlatılıyor..."
  python handler.py
else
  echo "► Mod: Standalone Pod (FastAPI)"
  echo "► FastAPI sunucusu başlatılıyor..."
  # API portunu 8080 olarak varsayıyoruz, RunPod Pod'larda genelde bu port kullanılır.
  python api.py
fi
