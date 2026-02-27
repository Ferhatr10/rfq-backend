import base64
import logging
import os
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from extractor import process_rfq

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Docling RFQ Processor API")

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
        model = os.getenv("OLLAMA_MODEL", "llama3")
        
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
