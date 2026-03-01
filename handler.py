import base64
import logging
import time

import runpod

from extractor import process_rfq

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def handler(job):
    """
    RunPod Serverless handler.

    Expected input:
    {
        "input": {
            "pdf_base64": "<base64 encoded PDF>",
            "filename": "rfq.pdf"   (optional)
        }
    }
    """
    job_input = job.get("input", {})

    # ── Validation ────────────────────────────────────────────────────────────────────
    pdf_base64 = job_input.get("pdf_base64")
    if not pdf_base64:
        return {"error": "pdf_base64 field is required."}

    filename = job_input.get("filename", "upload.pdf")

    # ── PDF decode ────────────────────────────────────────────────────────────
    try:
        file_bytes = base64.b64decode(pdf_base64)
    except Exception as e:
        return {"error": f"Base64 decode error: {str(e)}"}

    log.info(f"Processing started: {filename} ({len(file_bytes) / 1024 / 1024:.2f} MB)")
    start = time.time()

    # ── Extraction ────────────────────────────────────────────────────────────
    try:
        import os
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")
        result = process_rfq(file_bytes, ollama_url, model)
    except Exception as e:
        log.error(f"Error: {e}")
        return {"error": str(e)}

    elapsed = round(time.time() - start, 2)
    log.info(f"Completed: {elapsed}s")

    return {
        "success": True,
        "file": filename,
        "elapsed_seconds": elapsed,
        "data": result,
    }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
