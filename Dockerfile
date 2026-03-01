FROM python:3.11-slim

# System dependencies (for Docling, OCR & PostgreSQL)
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libgomp1 curl zstd procps build-essential git \
    tesseract-ocr libtesseract-dev \
    postgresql postgresql-contrib libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install pgvector (source-build)
RUN git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector && make && make install \
    && rm -rf /tmp/pgvector

# Install Ollama (will run within the same container)
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application files
COPY . .

# Pre-download Docling models (during build)
RUN python -c "from docling.document_converter import DocumentConverter; DocumentConverter()"

# Pre-download Ollama models (during build)
RUN ollama serve & \
    sleep 5 && \
    ollama pull llama3 && \
    pkill ollama

# Startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]