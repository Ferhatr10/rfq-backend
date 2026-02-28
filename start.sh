#!/bin/bash
set -e

# Default to Qwen 2.5 32B for high technical precision (128k context)
export OLLAMA_MODEL=${OLLAMA_MODEL:-"qwen2.5:32b"}
MODEL=$OLLAMA_MODEL

echo "► PostgreSQL başlatılıyor..."
# PostgreSQL servisinin başlamasını sağla
service postgresql start

echo "► Veritabanı yapılandırılıyor..."
# rfq_db adında veritabanını oluştur ve gerekli extension'ları ekle
su - postgres -c "psql -c 'CREATE DATABASE rfq_db;'" || echo "Veritabanı zaten mevcut olabilir."
su - postgres -c "psql -d rfq_db -c 'CREATE EXTENSION IF NOT EXISTS vector;'"
su - postgres -c "psql -d rfq_db -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm;'"

echo "► Ollama durumu kontrol ediliyor..."
if curl -sf http://localhost:11434/api/tags > /dev/null; then
  echo "► Ollama zaten çalışıyor."
else
  echo "► Ollama başlatılıyor..."
  ollama serve &
  # Ollama sunucusunun hazır olmasını bekle
  echo "► Ollama API bekleniyor..."
  until curl -sf http://localhost:11434/api/tags > /dev/null; do
    sleep 2
  done
fi

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

# Embedding modeli (RAG ve Hybrid Search için)
echo "► nomic-embed-text embedding modeli kontrol ediliyor..."
ollama pull nomic-embed-text
echo "► nomic-embed-text hazır!"

# Modeller artık imajın içinde (pre-baked), tekrar indirmeye gerek yok
# echo "► Model indiriliyor: $MODEL"
# ollama pull $MODEL

echo "► Başlatma modu kontrol ediliyor..."
if [ "$RUNPOD_SERVERLESS" = "true" ]; then
  echo "► Mod: RunPod Serverless"
  echo "► RunPod handler başlatılıyor..."
  python handler.py
else
  echo "► Mod: Standalone Pod (Streamlit Dashboard)"
  echo "► Streamlit dashboard başlatılıyor..."
  # RunPod proxy'si için CORS ve XSRF korumasını devre dışı bırakıyoruz (WebSocket hatasını çözer)
  streamlit run ui.py --server.port 8080 --server.address 0.0.0.0 --server.enableCORS false --server.enableXsrfProtection false
fi
