FROM python:3.11-slim

# Sistem bağımlılıkları (Docling için)
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

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

# Başlatma scripti
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
