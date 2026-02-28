import csv
import sys
import logging
from langchain_ollama import OllamaEmbeddings
from database import get_connection, init_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def ingest_csv(csv_path):
    # DB Hazırla
    init_db()
    
    # Embeddings setup
    # nomic-embed-text 768 boyuttur
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    
    conn = get_connection()
    cur = conn.cursor()
    
    log.info(f"Yükleme başlatılıyor: {csv_path}")
    
    import ast
    
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            # Görseldeki birebir sütun adlarına göre eşleme
            s_id = row.get('supplier_id')
            name = row.get('company_name', 'Bilinmeyen Tedarikçi')
            
            # Liste formatındaki verileri (['A', 'B']) güvenli bir şekilde parçala
            def parse_list(val):
                if not val: return []
                try:
                    # Temizlik: Eğer string olarak geliyorsa ve içinde [ ] varsa parse et
                    if isinstance(val, str) and '[' in val:
                        return ast.literal_eval(val)
                    return [i.strip() for i in val.split(',')]
                except:
                    return []

            capabilities = parse_list(row.get('capabilities'))
            materials = parse_list(row.get('materials'))
            certs = parse_list(row.get('certifications'))
            regu = parse_list(row.get('regulatory_compliance'))
            
            # Embedding için açıklama oluştur (Yetenekler + Materyaller birleştirilir)
            full_desc = f"Capabilities: {', '.join(capabilities)}. Materials: {', '.join(materials)}."
            
            sop_date = row.get('sop_date') if row.get('sop_date') else None
            try:
                rating = float(row.get('rating')) if row.get('rating') else 0.0
            except:
                rating = 0.0
            
            # Koordinat (lng olarak güncellendi)
            try:
                lat = float(row['lat']) if row.get('lat') else None
                lng = float(row['lng']) if row.get('lng') else None
            except:
                lat, lng = None, None
            
            # Vektör oluştur
            log.info(f"Vektör oluşturuluyor ({count+1}): {name}")
            vector = embeddings.embed_query(full_desc)
            
            # INSERT (Yeni sütunlar dahil)
            cur.execute("""
                INSERT INTO suppliers (supplier_id, name, certifications, regulatory, materials, sop_date, description, embedding, rating, lat, lng)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (s_id, name, certs, regu, materials, sop_date, full_desc, vector, rating, lat, lng))
            
            count += 1
            if count % 10 == 0:
                conn.commit()
                log.info(f"{count} kayıt işlendi...")
                
    conn.commit()
    cur.close()
    conn.close()
    log.info(f"Yükleme tamamlandı. Toplam {count} kayıt.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Kullanım: python ingest.py <csv_dosya_yolu>")
    else:
        ingest_csv(sys.argv[1])
