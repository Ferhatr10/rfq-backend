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

@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Docling RFQ Extractor</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #6366f1;
                --primary-hover: #4f46e5;
                --bg: #0f172a;
                --card: #1e293b;
                --text: #f1f5f9;
                --text-muted: #94a3b8;
                --accent: #22d3ee;
            }
            body { 
                font-family: 'Inter', sans-serif; 
                background-color: var(--bg); 
                color: var(--text); 
                margin: 0; 
                display: flex; 
                justify-content: center; 
                align-items: center; 
                min-height: 100vh;
                background-image: radial-gradient(circle at top right, #1e1b4b, transparent), radial-gradient(circle at bottom left, #1e1b4b, transparent);
            }
            .container { 
                width: 90%; 
                max-width: 800px; 
                background: var(--card); 
                padding: 2.5rem; 
                border-radius: 24px; 
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                border: 1px solid rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
            }
            h1 { font-weight: 700; margin-bottom: 0.5rem; background: linear-gradient(to right, var(--primary), var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            p { color: var(--text-muted); margin-bottom: 2rem; }
            .upload-section { 
                border: 2px dashed rgba(255,255,255,0.2); 
                padding: 3rem; 
                text-align: center; 
                border-radius: 16px; 
                cursor: pointer; 
                transition: all 0.3s ease;
                background: rgba(255,255,255,0.02);
            }
            .upload-section:hover { border-color: var(--primary); background: rgba(99, 102, 241, 0.05); transform: translateY(-2px); }
            input[type="file"] { display: none; }
            .btn { 
                background: var(--primary); 
                color: white; 
                border: none; 
                padding: 0.75rem 1.5rem; 
                border-radius: 12px; 
                font-weight: 600; 
                cursor: pointer; 
                transition: all 0.2s;
                margin-top: 1rem;
            }
            .btn:hover { background: var(--primary-hover); box-shadow: 0 0 20px rgba(99, 102, 241, 0.4); }
            .btn:disabled { background: #475569; cursor: not-allowed; }
            #result { 
                margin-top: 2rem; 
                padding: 1.5rem; 
                background: #020617; 
                border-radius: 12px; 
                max-height: 400px; 
                overflow-y: auto; 
                display: none;
                border: 1px solid rgba(255,255,255,0.05);
            }
            pre { margin: 0; color: #34d399; font-family: 'Fira Code', monospace; font-size: 0.9rem; }
            .loader { 
                display: none; 
                width: 24px; height: 24px; 
                border: 3px solid rgba(255,255,255,0.3); 
                border-radius: 50%; 
                border-top-color: #fff; 
                animation: spin 1s ease-in-out infinite;
                margin: 1rem auto;
            }
            @keyframes spin { to { transform: rotate(360deg); } }
            .swagger-link { display: block; margin-top: 2rem; text-align: center; color: var(--accent); text-decoration: none; font-size: 0.9rem; opacity: 0.7; transition: 0.2s; }
            .swagger-link:hover { opacity: 1; text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Docling RFQ AI Alpha</h1>
            <p>Upload a PDF document to extract structured RFQ fields using LangChain & local LLM.</p>
            
            <div class="upload-section" onclick="document.getElementById('fileInput').click()">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 1rem; color: var(--primary)"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                <div id="fileName">Select or Drop PDF</div>
                <input type="file" id="fileInput" accept=".pdf" onchange="updateFileName()">
            </div>
            
            <div style="text-align: center;">
                <button class="btn" id="uploadBtn" onclick="uploadFile()">Extract Data</button>
                <div class="loader" id="loader"></div>
            </div>

            <div id="result">
                <pre id="jsonOutput"></pre>
            </div>

            <a href="/docs" class="swagger-link">Open API Documentation (Swagger)</a>
        </div>

        <script>
            function updateFileName() {
                const input = document.getElementById('fileInput');
                document.getElementById('fileName').innerText = input.files[0] ? input.files[0].name : 'Select or Drop PDF';
            }

            async function uploadFile() {
                const fileInput = document.getElementById('fileInput');
                if (!fileInput.files[0]) return alert('Please select a file first!');
                
                const btn = document.getElementById('uploadBtn');
                const loader = document.getElementById('loader');
                const resultDiv = document.getElementById('result');
                const jsonOutput = document.getElementById('jsonOutput');

                btn.disabled = true;
                loader.style.display = 'block';
                resultDiv.style.display = 'none';

                const file = fileInput.files[0];
                const reader = new FileReader();
                reader.onload = async function() {
                    const base64Content = reader.result.split(',')[1];
                    try {
                        const response = await fetch('/process', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                pdf_base64: base64Content,
                                filename: file.name
                            })
                        });
                        const data = await response.json();
                        jsonOutput.innerText = JSON.stringify(data, null, 2);
                        resultDiv.style.display = 'block';
                    } catch (err) {
                        alert('Error: ' + err.message);
                    } finally {
                        btn.disabled = false;
                        loader.style.display = 'none';
                    }
                };
                reader.readAsDataURL(file);
            }
        </script>
    </body>
    </html>
    """

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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
