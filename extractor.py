import logging
import tempfile
from pathlib import Path
from typing import List, Dict, Any

from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

from schema import Pass1Extraction, SupplierSearchProfile
from prompt import (
    PASS1_SYSTEM_PROMPT, PASS1_USER_PROMPT,
    PASS2_SYSTEM_PROMPT, PASS2_USER_PROMPT,
)

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
PASS1_MODEL   = "qwen2.5:14b"
PASS2_MODEL   = "qwen2.5:14b"
EMBED_MODEL   = "sentence-transformers/all-MiniLM-L6-v2"   # sadece tokenizer için
MAX_TOKENS    = 1500        # HybridChunker token limiti
SUPER_CHUNK_SIZE = 8000     # LLM'e gönderilecek birleştirilmiş maksimum karakter sınırı


# ─────────────────────────────────────────────────────────────────────────────
# DOCLING — hız odaklı OCR-sız converter
# ─────────────────────────────────────────────────────────────────────────────
def get_fast_converter() -> DocumentConverter:
    """Docling'i OCR'sız (yüksek hız) yapılandırır. Doğal PDF'ler için idealdir."""
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False

    return DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    })


# ─────────────────────────────────────────────────────────────────────────────
# PASS 1 HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def merge_pass1_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Pass 1 sonuçlarını birleştirir.
    - Tekil alanlar  → son dolu değeri alır
    - Liste alanları → birleştirir + deduplicate
    """
    merged: Dict[str, Any] = {
        "component_name": None,
        "material_specifications": [],
        "certifications_mentioned": [],
        "weight_and_dimensions": None,
        "surface_treatments": [],
    }

    for res in results:
        if res.get("component_name"):
            merged["component_name"] = res["component_name"]
        if res.get("weight_and_dimensions"):
            merged["weight_and_dimensions"] = res["weight_and_dimensions"]

        for field in ("material_specifications", "certifications_mentioned", "surface_treatments"):
            vals = res.get(field)
            if vals and isinstance(vals, list):
                merged[field].extend(vals)

    # Deduplicate
    for key in ("material_specifications", "certifications_mentioned", "surface_treatments"):
        merged[key] = list(set(merged[key]))

    return merged


# ─────────────────────────────────────────────────────────────────────────────
# CORE — Two-Pass Extraction
# ─────────────────────────────────────────────────────────────────────────────
def extract_with_langchain(file_bytes: bytes, ollama_url: str) -> dict:
    """
    Two-Pass Agentic RAG:
        Pass 1 (qwen2.5:14b) — Map:    Her chunk'tan ham veri çıkar
        Pass 2 (qwen2.5:14b) — Reduce: Ham verileri SupplierSearchProfile'a sentezle
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        # ── 1. LOAD — DOC_CHUNKS modu ────────────────────────────────────────
        converter = get_fast_converter()
        loader = DoclingLoader(
            file_path=str(tmp_path),
            converter=converter,
            export_type=ExportType.DOC_CHUNKS,
            chunker=HybridChunker(
                tokenizer=EMBED_MODEL,
                max_tokens=MAX_TOKENS,
                merge_peers=True,
            ),
        )
        docs = loader.load()
        log.info(f"Docling dokümanı böldü: {len(docs)} küçük chunk")

        # ── YENİ: CONTEXT PACKING (Süper-Chunk Oluşturma) ────────────────────
        # 300 tokenlik küçük parçaları ~8000 karakterlik devasa bloklar halinde birleştiriyoruz.
        packed_chunks = []
        current_super_chunk = ""

        for doc in docs:
            # Sınırı aşmıyorsa birleştir
            if len(current_super_chunk) + len(doc.page_content) < SUPER_CHUNK_SIZE:
                if current_super_chunk:
                    current_super_chunk += "\n\n---\n\n"
                current_super_chunk += doc.page_content
            else:
                # Sınır aşıldıysa paketle ve yeni bir pakete başla
                if current_super_chunk:
                    packed_chunks.append(current_super_chunk)
                current_super_chunk = doc.page_content

        # Kalan son parçayı da ekle
        if current_super_chunk.strip():
            packed_chunks.append(current_super_chunk)

        log.info(f"Paketleme tamamlandı: {len(docs)} küçük chunk, {len(packed_chunks)} Süper-Chunk'a birleştirildi.")

        # ── 2. PASS 1 — THE EXTRACTOR (Map Phase) ────────────────────────────
        extractor_llm = ChatOllama(
            model=PASS1_MODEL,
            base_url=ollama_url,
            format="json",
            temperature=0,
        )
        structured_extractor = extractor_llm.with_structured_output(Pass1Extraction)
        extractor_chain = (
            ChatPromptTemplate.from_messages([
                ("system", PASS1_SYSTEM_PROMPT),
                ("user",   PASS1_USER_PROMPT),
            ])
            | structured_extractor
        )

        raw_results: List[Dict[str, Any]] = []
        
        # Artık küçük doc'larda değil, bizim hazırladığımız geniş bağlamlı Süper-Chunk'larda dönüyoruz
        for idx, super_chunk_text in enumerate(packed_chunks):
            log.info(f"Pass 1 — Süper-Chunk {idx + 1}/{len(packed_chunks)} işleniyor "
                     f"({len(super_chunk_text)} chars)")
            try:
                res = extractor_chain.invoke({"markdown_chunk_text": super_chunk_text})
                raw_results.append(res.model_dump())
            except Exception as e:
                log.warning(f"  Süper-Chunk {idx + 1} atlandı: {e}")

        # ── 3. MERGE ──────────────────────────────────────────────────────────
        merged_data = merge_pass1_results(raw_results)
        log.info(f"Pass 1 tamamlandı — {len(raw_results)} Süper-Chunk sonucu birleştirildi.")

        # ── 4. PASS 2 — THE ORGANIZER (Reduce Phase) ─────────────────────────
        organizer_llm = ChatOllama(
            model=PASS2_MODEL,
            base_url=ollama_url,
            format="json",
            temperature=0.1,
        )
        structured_organizer = organizer_llm.with_structured_output(SupplierSearchProfile)
        organizer_chain = (
            ChatPromptTemplate.from_messages([
                ("system", PASS2_SYSTEM_PROMPT),
                ("user",   PASS2_USER_PROMPT),
            ])
            | structured_organizer
        )

        log.info("Pass 2 başlatılıyor — SupplierSearchProfile sentezleniyor…")
        final_profile: SupplierSearchProfile = organizer_chain.invoke(
            {"merged_json_from_pass_1": str(merged_data)}
        )

        return final_profile.model_dump()

    except Exception as e:
        log.error(f"Two-Pass Extraction hatası: {e}")
        raise
    finally:
        tmp_path.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def process_rfq(file_bytes: bytes, ollama_url: str, model: str = None) -> dict:
    """Ana giriş noktası. api.py ve handler.py bu fonksiyonu çağırır."""
    return extract_with_langchain(file_bytes, ollama_url)