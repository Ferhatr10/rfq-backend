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

    Beklenen input:
    {
        "input": {
            "pdf_base64": "<base64 encoded PDF>",
            "filename": "rfq.pdf"   (opsiyonel)
        }
    }
    """
    job_input = job.get("input", {})

    # ── Validasyon ────────────────────────────────────────────────────────────
    pdf_base64 = job_input.get("pdf_base64")
    if not pdf_base64:
        return {"error": "pdf_base64 alanı zorunludur."}

    filename = job_input.get("filename", "upload.pdf")

    # ── PDF decode ────────────────────────────────────────────────────────────
    try:
        file_bytes = base64.b64decode(pdf_base64)
    except Exception as e:
        return {"error": f"Base64 decode hatası: {str(e)}"}

    log.info(f"İşlem başladı: {filename} ({len(file_bytes) / 1024 / 1024:.2f} MB)")
    start = time.time()

    # ── Extraction ────────────────────────────────────────────────────────────
    try:
        import os
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3")
        result = process_rfq(file_bytes, ollama_url, model)
    except Exception as e:
        log.error(f"Hata: {e}")
        return {"error": str(e)}

    elapsed = round(time.time() - start, 2)
    log.info(f"Tamamlandı: {elapsed}s")

    return {
        "success": True,
        "file": filename,
        "elapsed_seconds": elapsed,
        "data": result,
    }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
