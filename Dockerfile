FROM python:3.11-slim

# Sistem bağımlılıkları (Docling, OCR & PostgreSQL için)
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libgomp1 curl zstd procps build-essential git \
    tesseract-ocr libtesseract-dev \
    postgresql postgresql-contrib libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# pgvector kur (source-build)
RUN git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector && make && make install \
    && rm -rf /tmp/pgvector

# Ollama kur (aynı container içinde çalışacak)
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

# Python bağımlılıkları
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyaları
COPY . .

# Docling modellerini önceden indir (build sırasında)
RUN python -c "from docling.document_converter import DocumentConverter; DocumentConverter()"

# Ollama modellerini önceden indir (build sırasında)
RUN ollama serve & \
    sleep 5 && \
    ollama pull llama3 && \
    pkill ollama

# Başlatma scripti
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]