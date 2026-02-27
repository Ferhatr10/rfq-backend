import json
import logging
import tempfile
from pathlib import Path

import httpx
from docling.document_converter import DocumentConverter

from schema import RFQ_FIELDS
from prompt import SYSTEM_PROMPT, USER_PROMPT

log = logging.getLogger(__name__)

# ── Docling converter (uygulama başlarken bir kere yüklenir) ──────────────────
converter = DocumentConverter()


def parse_pdf(file_bytes: bytes) -> str:
    """PDF'i Docling ile metne çevirir."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        result = converter.convert(str(tmp_path))
        text = result.document.export_to_markdown()
        log.info(f"PDF parse edildi, karakter sayısı: {len(text)}")
        return text
    finally:
        tmp_path.unlink(missing_ok=True)


def build_fields_description() -> str:
    """Schema'dan LLM için alan listesi oluşturur."""
    lines = []
    for field, description in RFQ_FIELDS.items():
        lines.append(f'- "{field}": {description}')
    return "\n".join(lines)


def extract_with_ollama(text: str, ollama_url: str, model: str) -> dict:
    """Ollama ile metinden RFQ alanlarını çıkarır."""
    fields_desc = build_fields_description()
    user_message = USER_PROMPT.format(fields=fields_desc, text=text[:8000])  # token limiti

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {"role": "user", "content": user_message.strip()},
        ],
        "stream": False,
        "format": "json",  # Ollama'ya JSON çıktısı zorla
    }

    response = httpx.post(
        f"{ollama_url}/api/chat",
        json=payload,
        timeout=120.0,
    )
    
    # Model henüz yükleniyorsa Ollama hata dönebilir veya boş kalabilir
    if response.status_code != 200:
        log.error(f"Ollama hata döndü ({response.status_code}): {response.text}")
        raise ValueError(f"Ollama servisi hazır değil: {response.text}")

    content = response.json().get("message", {}).get("content", "")
    if not content:
        log.warning("Ollama'dan boş yanıt geldi! Model hala yükleniyor olabilir.")
        raise ValueError("Ollama boş yanıt döndü.")

    log.info(f"Ollama yanıtı: {content[:200]}")

    # JSON parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # LLM bazen ```json ... ``` sarıyor, temizle
        import re
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Geçerli JSON bulunamadı: {content}")


def process_rfq(file_bytes: bytes, ollama_url: str, model: str) -> dict:
    """Ana fonksiyon: PDF → metin → JSON."""
    # 1. PDF'i metne çevir
    text = parse_pdf(file_bytes)

    # 2. Ollama ile çıkarım yap
    extracted = extract_with_ollama(text, ollama_url, model)

    # 3. Schema'daki tüm alanların varlığını garantile (eksikleri null yap)
    result = {field: extracted.get(field) for field in RFQ_FIELDS}

    return result
