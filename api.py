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

app = FastAPI(
    title="RFQ Intelligence & Supplier Discovery API",
    description="Automated RFQ data extraction and hybrid supplier search engine.",
    version="2.0.0"
)

@app.on_event("startup")
def startup_event():
    from database import init_db
    init_db()
    log.info("Database initialized successfully.")

@app.get("/")
def root():
    return {"message": "RFQ Intelligence API is online. Access /docs for documentation."}

class RFQRequest(BaseModel):
    pdf_base64: str
    filename: str = "upload.pdf"

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/extract-pdf", tags=["Extraction"])
async def extract_pdf(file: UploadFile = File(...)):
    """
    Direct PDF upload endpoint. 
    Accepts raw multipart/form-data. Base64 encoding NOT required.
    """
    file_bytes = await file.read()
    log.info(f"Direct upload started: {file.filename} ({len(file_bytes) / 1024 / 1024:.2f} MB)")
    
    start_time = time.time()
    try:
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        result = process_rfq(file_bytes, ollama_url, model)
        
        elapsed = round(time.time() - start_time, 2)
        return {
            "success": True,
            "filename": file.filename,
            "elapsed_seconds": elapsed,
            "data": result
        }
    except Exception as e:
        log.error(f"Extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process", tags=["Extraction"], include_in_schema=False)
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
        model = os.getenv("OLLAMA_MODEL", "qwen.2.5:14b")
        
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
    countries: list[str] = []
    near_city: str = None
    radius_km: float = None
    strict_mode: bool = True
    top_k: int = 5

@app.post("/discovery", tags=["Discovery"])
def hybrid_search(request: SearchRequest):
    """
    Hybrid search endpoint.
    - strict_mode=true: Excludes suppliers not meeting criteria.
    - strict_mode=false: Includes all suppliers, scored with match bonus.
    """
    try:
        from search import HybridSearchEngine
        engine = HybridSearchEngine()
        results = engine.search(
            query=request.query, 
            certs=request.certifications, 
            regs=request.regulatory, 
            near_city=request.near_city,
            radius_km=request.radius_km,
            countries=request.countries,
            strict_mode=request.strict_mode,
            top_k=request.top_k
        )
        return {"success": True, "results": results}
    except Exception as e:
        log.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metadata", tags=["Discovery"])
def get_metadata():
    """
    Returns unique metadata values for filtering:
    - Countries
    - Cities
    - Certifications (Unnested)
    - Regulatory (Unnested)
    """
    try:
        from database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        
        # Unique Countries
        cur.execute("SELECT DISTINCT country FROM suppliers WHERE country IS NOT NULL ORDER BY country;")
        countries = [r[0] for r in cur.fetchall()]
        
        # Unique Cities
        cur.execute("SELECT DISTINCT city FROM suppliers WHERE city IS NOT NULL ORDER BY city;")
        cities = [r[0] for r in cur.fetchall()]
        
        # Unique Certifications
        cur.execute("SELECT DISTINCT unnest(certifications) as cert FROM suppliers WHERE certifications IS NOT NULL ORDER BY cert;")
        certs = [r[0] for r in cur.fetchall()]
        
        # Unique Regulatory
        cur.execute("SELECT DISTINCT unnest(regulatory) as reg FROM suppliers WHERE regulatory IS NOT NULL ORDER BY reg;")
        regs = [r[0] for r in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "countries": countries,
            "cities": cities,
            "certifications": certs,
            "regulatory": regs
        }
    except Exception as e:
        log.error(f"Metadata error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest-file", tags=["Ingestion"])
async def ingest_file(file: UploadFile = File(...)):
    """
    Remote file upload endpoint (CSV, JSON, SQLite).
    """
    import tempfile
    from pathlib import Path
    from ingest import ingest_csv, ingest_json, ingest_sqlite
    
    file_bytes = await file.read()
    ext = os.path.splitext(file.filename)[1].lower()
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)
        
    try:
        if ext == '.csv':
            ingest_csv(str(tmp_path))
        elif ext == '.json':
            ingest_json(str(tmp_path))
        elif ext in ['.db', '.sqlite', '.sqlite3']:
            ingest_sqlite(str(tmp_path))
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format.")
            
        return {"success": True, "message": f"{file.filename} processed successfully."}
    except Exception as e:
        log.error(f"Ingest file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

@app.post("/ingest-data", tags=["Ingestion"])
def ingest_data(data: list[dict]):
    """
    Data ingestion endpoint via direct JSON list.
    """
    try:
        from ingest import process_records
        process_records(data)
        return {"success": True, "message": f"{len(data)} records ingested successfully."}
    except Exception as e:
        log.error(f"Ingest data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest", tags=["Ingestion"], deprecated=True)
def trigger_ingest(csv_path: str):
    """
    Legacy method: Triggers ingestion via local file path.
    """
    try:
        from ingest import ingest_csv, ingest_json, ingest_sqlite
        if not os.path.exists(csv_path):
            raise HTTPException(status_code=404, detail="File not found.")
        
        ext = os.path.splitext(csv_path)[1].lower()
        if ext == '.csv':
            ingest_csv(csv_path)
        elif ext == '.json':
            ingest_json(csv_path)
        elif ext in ['.db', '.sqlite', '.sqlite3']:
            ingest_sqlite(csv_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid file extension.")
            
        return {"success": True, "message": "Ingestion completed successfully."}
    except Exception as e:
        log.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reset-db", tags=["Maintenance"])
def reset_db():
    """
    Deletes all supplier data from the database.
    """
    try:
        from database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE suppliers RESTART IDENTITY;")
        conn.commit()
        cur.close()
        conn.close()
        return {"success": True, "message": "All data deleted, database reset."}
    except Exception as e:
        log.error(f"Reset DB error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
