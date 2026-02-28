import base64
import logging
import os
import time
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from extractor import process_rfq

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Docling RFQ Processor API")

@app.get("/")
def root():
    return {"message": "Docling RFQ Processor API is running. Use Streamlit UI for interaction."}

class RFQRequest(BaseModel):
    pdf_base64: str
    filename: str = "upload.pdf"

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/process")
def process_pdf(request: RFQRequest):
    """
    HTTP endpoint for regular Pod execution.
    Matches the input structure of the Serverless handler.
    """
    try:
        # Decode base64
        file_bytes = base64.b64decode(request.pdf_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Base64 decode error: {str(e)}")

    log.info(f"Processing started via API: {request.filename} ({len(file_bytes) / 1024 / 1024:.2f} MB)")
    start_time = time.time()

    try:
        # Environment variables for Ollama
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")
        
        # Core processing logic
        result = process_rfq(file_bytes, ollama_url, model)
        
        elapsed = round(time.time() - start_time, 2)
        log.info(f"Processing completed in {elapsed}s")

        return {
            "success": True,
            "file": request.filename,
            "elapsed_seconds": elapsed,
            "data": result,
        }
    except Exception as e:
        log.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class SearchRequest(BaseModel):
    query: str
    certifications: list[str] = []
    regulatory: list[str] = []
    strict_mode: bool = True  # Yeni eklenen parametre (Varsayılan: True)
    top_k: int = 5

@app.post("/search")
def search_suppliers(request: SearchRequest):
    """
    Hibrit arama endpoint'i.
    - strict_mode=true: Kriterlere uymayanları eler.
    - strict_mode=false: Herkesi puanlayarak getirir.
    """
    try:
        from search import HybridSearchEngine
        engine = HybridSearchEngine()
        results = engine.search(
            query=request.query, 
            certs=request.certifications, 
            regs=request.regulatory, 
            strict_mode=request.strict_mode,
            top_k=request.top_k
        )
        return {"success": True, "results": results}
    except Exception as e:
        log.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest")
def trigger_ingest(csv_path: str):
    """
    Manuel veri yükleme tetikleyicisi.
    """
    try:
        from ingest import ingest_csv
        if not os.path.exists(csv_path):
            raise HTTPException(status_code=404, detail="CSV dosyası bulunamadı.")
        
        # Arka planda çalıştırılabilir ama şimdilik senkron
        ingest_csv(csv_path)
        return {"success": True, "message": "Veriler başarıyla yüklendi."}
    except Exception as e:
        log.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
