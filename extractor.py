import logging
import tempfile
from pathlib import Path

from langchain_docling import DoclingLoader
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from schema import RFQResponse, RFQ_FIELDS
from prompt import SYSTEM_PROMPT

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions, RapidOcrOptions

log = logging.getLogger(__name__)

def get_optimized_converter():
    """Docling'i yüksek hassasiyetli OCR (EasyOCR) ile yapılandırır."""
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    
    # EasyOCR, tesserocr'ın kurulum hatalarından kaçınmak için güçlü bir alternatiftir.
    ocr_options = EasyOcrOptions()
    ocr_options.lang = ["en", "de"]
    ocr_options.force_full_page_ocr = True  # KRİTİK: Bozuk text layer'ı atla ve her sayfada gerçek OCR yap
    pipeline_options.ocr_options = ocr_options
    
    return DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    })

def extract_with_langchain(file_bytes: bytes, ollama_url: str, model: str) -> dict:
    """PDF'i yapılandırılmış OCR ile yükler, parçalara böler ve LangChain + Ollama ile veri çıkarır."""
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        # Standart DoclingLoader yerine optimize edilmiş converter kullanıyoruz
        converter = get_optimized_converter()
        loader = DoclingLoader(file_path=str(tmp_path), converter=converter)
        
        docs = loader.load()
        full_text = "\n\n".join([doc.page_content for doc in docs])
        log.info(f"Doküman yüklendi, toplam karakter: {len(full_text)}")
        
        # DEBUG: Raw metni konsola da yaz ki serverda dosya aramayalım
        log.info(f"--- HAM METİN BAŞLANGICI (İLK 1000 KRK) ---\n{full_text[:1000]}\n--- HAM METİN SONU ---")
        
        # DEBUG: Raw text'i dosyaya yaz
        debug_path = Path("debug_raw_text.md")
        debug_path.write_text(full_text, encoding="utf-8")
        log.info(f"Ham metin debug için kaydedildi: {debug_path.absolute()}")

        llm = ChatOllama(model=model, base_url=ollama_url, format="json", temperature=0)
        structured_llm = llm.with_structured_output(RFQResponse)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", "Extract RFQ details from this document chunk:\n\n{text}"),
        ])
        chain = prompt | structured_llm

        # Chunking ayarları (Granite 3.1 128k context desteğine sahip)
        # 32.000 karakter (~8k-10k token) güvenli ve hızlı bir aralıktır
        chunk_size = 32000
        overlap = 4000
        chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size - overlap)]
        
        log.info(f"Doküman {len(chunks)} parçaya bölündü.")
        
        # Sonuçları biriktirmek için boş bir yapı oluştur (null/0 confidence ile)
        final_data = {}
        # RFQResponse alanlarını örnekleyerek başla
        empty_response = RFQResponse.model_construct()
        for field_name in empty_response.model_fields:
            final_data[field_name] = {"value": None, "confidence": 0}

        # Parça parça döngü
        for idx, chunk_text in enumerate(chunks):
            log.info(f"Parça {idx+1}/{len(chunks)} işleniyor...")
            try:
                # Sadece doküman çok uzunsa ilk 10 parçayı işle (zaman/performans için koruma)
                if idx >= 15: 
                    log.warning("Çok uzun doküman, güvenlik sınırı (15 parça) nedeniyle durduruldu.")
                    break

                response = chain.invoke({"text": chunk_text})
                chunk_results = response.model_dump()

                # Merge Logic
                for field_name, result in chunk_results.items():
                    current = final_data[field_name]
                    new_val = result["value"]
                    new_conf = result["confidence"]

                    if new_val is None:
                        continue

                    # Liste tipi alanlar için (birleştir ve deduplicate)
                    if isinstance(new_val, list):
                        if not isinstance(current["value"], list):
                            current["value"] = []
                        
                        # Mevcut liste ile yeni listeyi birleştir ve kopyala (tekrarları temizle)
                        combined_list = list(set(current["value"] + new_val))
                        current["value"] = combined_list
                        current["confidence"] = max(current["confidence"], new_conf)
                    
                    # Tekil alanlar için (en yüksek güven puanını tut)
                    else:
                        if new_conf > current["confidence"]:
                            final_data[field_name] = result
            
            except Exception as chunk_err:
                log.warning(f"Parça {idx+1} işlenirken hata oluştu (atlanıyor): {chunk_err}")
                import traceback
                log.debug(traceback.format_exc())
                continue

        return final_data

    except Exception as e:
        log.error(f"LangChain extraction hatası: {e}")
        raise
    finally:
        tmp_path.unlink(missing_ok=True)


def process_rfq(file_bytes: bytes, ollama_url: str, model: str) -> dict:
    """Ana fonksiyon: PDF → LangChain → JSON."""
    return extract_with_langchain(file_bytes, ollama_url, model)
