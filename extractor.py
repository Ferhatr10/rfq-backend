import logging
import tempfile
from pathlib import Path

from langchain_docling import DoclingLoader
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from schema import RFQResponse, RFQ_FIELDS
from prompt import SYSTEM_PROMPT

log = logging.getLogger(__name__)

def extract_with_langchain(file_bytes: bytes, ollama_url: str, model: str) -> dict:
    """PDF'i DoclingLoader ile yükler ve LangChain + Ollama ile yapılandırılmış veri çıkarır."""
    
    # 1. PDF'i geçici dosyaya yaz (DoclingLoader dosya yolu bekler)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        # 2. DoclingLoader ile dokümanı yükle
        loader = DoclingLoader(file_path=str(tmp_path))
        docs = loader.load()
        
        # Tüm sayfaları birleştir
        full_text = "\n\n".join([doc.page_content for doc in docs])
        log.info(f"Doküman yüklendi, karakter sayısı: {len(full_text)}")

        # 3. ChatOllama yapılandırması
        llm = ChatOllama(
            model=model,
            base_url=ollama_url,
            format="json",
            temperature=0,
        )
        
        # Yapılandırılmış çıktı (Structured Output) tanımlanması
        structured_llm = llm.with_structured_output(RFQResponse)

        # 4. Prompt hazırlama
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", "Extract RFQ details from the following document:\n\n{text}"),
        ])

        # 5. Chain oluşturma ve çalıştırma
        chain = prompt | structured_llm
        
        # Token limitine dikkat ederek veriyi gönder
        response = chain.invoke({"text": full_text[:12000]})
        
        # 6. Sonucu dict olarak döndür (null kontrolü Pydantic tarafından yapılıyor)
        return response.model_dump()

    except Exception as e:
        log.error(f"LangChain extraction hatası: {e}")
        raise
    finally:
        tmp_path.unlink(missing_ok=True)


def process_rfq(file_bytes: bytes, ollama_url: str, model: str) -> dict:
    """Ana fonksiyon: PDF → LangChain → JSON."""
    return extract_with_langchain(file_bytes, ollama_url, model)
