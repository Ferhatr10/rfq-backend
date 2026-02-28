import streamlit as st
import pandas as pd
import os
import json
from search import HybridSearchEngine
from extractor import process_rfq
import logging

# Sayfa yapılandırması
st.set_page_config(page_title="AI Supply Chain Dashboard", layout="wide")

# Sidebar - Genel Ayarlar
st.sidebar.title("⚙️ Global Settings")
ollama_url = st.sidebar.text_input("Ollama URL", value="http://localhost:11434")
ollama_model = st.sidebar.text_input("Extraction Model", value="qwen2.5:32b")

# Başlık
st.title("🤖 AI-Powered RFQ & Supplier Discovery")

# Sekmeler (Tabs)
tab_extract, tab_search = st.tabs(["📄 RFQ Extraction", "🔍 Supplier Discovery"])

# --- TAB 1: RFQ EXTRACTION ---
with tab_extract:
    st.header("Upload RFQ Document")
    st.markdown("Doküman yükleyerek içindeki teknik verileri (materyal, tolerans, sertifika vb.) otomatik çıkarın.")
    
    uploaded_file = st.file_uploader("Select PDF", type=["pdf"])
    
    if uploaded_file is not None:
        if st.button("Extract Data 🚀", key="btn_extract"):
            with st.spinner("AI is reading the document... This may take a minute."):
                try:
                    file_bytes = uploaded_file.read()
                    result = process_rfq(file_bytes, ollama_url, ollama_model)
                    
                    st.success("Extraction Complete!")
                    
                    # Sonuçları Görselleştir
                    col1, col2 = st.columns(2)
                    
                    # Basitleştirilmiş Tablo Görünümü
                    extracted_data = []
                    for field, data in result.items():
                        val = data.get("value")
                        conf = data.get("confidence", 0)
                        extracted_data.append({
                            "Field": field.replace("_", " ").title(),
                            "Value": str(val) if val else "Not Found",
                            "Confidence": f"%{conf*100:.0f}"
                        })
                    
                    df = pd.DataFrame(extracted_data)
                    
                    with col1:
                        st.subheader("Extracted Details")
                        st.table(df)
                    
                    with col2:
                        st.subheader("Raw JSON Output")
                        st.json(result)
                        
                        # Arama için öneri (Query oluştur)
                        suggested_query = ""
                        if result.get("material_type", {}).get("value"):
                            suggested_query += f"{result['material_type']['value']} "
                        if result.get("manufacturing_process", {}).get("value"):
                            suggested_query += f"{result['manufacturing_process']['value']} "
                        
                        if suggested_query:
                            st.info(f"💡 **Suggested Search Query:** {suggested_query}")

                except Exception as e:
                    st.error(f"Extraction failed: {e}")

# --- TAB 2: SUPPLIER DISCOVERY ---
with tab_search:
    st.header("Discovery & Hybrid Search")
    st.markdown("Tedarikçi havuzunda akıllı arama yapın.")

    # Arama Motorunu Başlat
    @st.cache_resource
    def get_engine():
        return HybridSearchEngine()

    try:
        engine = get_engine()
        
        # Arama Parametreleri
        col_q, col_opt = st.columns([3, 1])
        
        with col_q:
            query = st.text_area("Yetenek / Materyal Sorgusu", 
                                placeholder="Örn: high precision aluminum casting...",
                                height=100)
            
            # Örnek Sertifika ve Regülasyon Listeleri
            all_certs = ["ISO 9001", "ISO 14001", "IATF 16949", "AS9100D", "ISO 45001"]
            all_regs = ["RoHS", "REACH", "Conflict Minerals", "TSCA", "VDA 6.3", "CE", "UL"]
            
            c1, c2 = st.columns(2)
            with c1:
                selected_certs = st.multiselect("Sertifika Kriterleri", all_certs)
            with c2:
                selected_regs = st.multiselect("Regülasyon Kriterleri", all_regs)

        with col_opt:
            strict_mode = st.toggle("Strict Mode (Tam Eşleşme)", value=True)
            top_k = st.slider("Sonuç Sayısı", 1, 20, 5)
            st.write("---")
            search_btn = st.button("Tedarikçileri Bul 🔍", use_container_width=True)

        # Arama Sonuçları
        if search_btn:
            if not query:
                st.warning("Lütfen bir arama sorgusu girin.")
            else:
                with st.spinner("Tedarikçiler analiz ediliyor..."):
                    results = engine.search(
                        query=query,
                        certs=selected_certs,
                        regs=selected_regs,
                        strict_mode=strict_mode,
                        top_k=top_k
                    )

                if not results:
                    st.info("Kriterlere uygun tedarikçi bulunamadı. Filtreleri gevşetmeyi deneyin.")
                else:
                    st.success(f"{len(results)} tedarikçi bulundu!")
                    
                    for res in results:
                        with st.container():
                            r_col1, r_col2 = st.columns([3, 1])
                            
                            with r_col1:
                                st.subheader(f"{res['name']} ({res['supplier_id']})")
                                st.write(f"**Description:** {res['description_preview']}")
                                
                                c_tags = " ".join([f"`{c}`" for c in res['certifications']])
                                r_tags = " ".join([f"`{r}`" for r in res['regulatory_compliance']])
                                st.markdown(f"**Certs:** {c_tags} | **Regs:** {r_tags}")
                                st.markdown(f"**Materials:** {', '.join(res['materials'])}")
                            
                            with r_col2:
                                st.metric("Suitability", f"{res['scores']['total_suitability']:.4f}")
                                st.write(f"⭐ Rating: {res['rating']}")
                                st.progress(min(res['scores']['vector_similarity'], 1.0), text=f"Semantic: {res['scores']['vector_similarity']:.2f}")
                            
                            st.divider()

    except Exception as e:
        st.error(f"Search engine error: {e}")

# Alt Bilgi
st.markdown("---")
st.caption("AI-Powered Supply Chain Alpha v2.0")
