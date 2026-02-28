import os
import psycopg2
from psycopg2.extras import execute_values
import numpy as np

# DB Connection settings (internal)
# Sunucuda çalıştığınız için host ve port belirtmezsek Unix Socket üzerinden bağlanır.
# Ancak bazen yetki sorunları nedeniyle şifre isteyebilir, bu yüzden localhost + şifre ekliyoruz.
DB_CONFIG = {
    "dbname": "rfq_db",
    "user": "postgres",
    "password": os.getenv("PGPASSWORD", "postgres"),
    "host": os.getenv("DB_HOST", "localhost")
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    """Tabloları ve extension'ları son kez kontrol eder/oluşturur."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Extension'lar zaten start.sh'de ama garanti olsun
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            supplier_id TEXT, -- SUP-1000 formatı
            name TEXT NOT NULL,
            certifications TEXT[],
            regulatory TEXT[],
            materials TEXT[],   -- Yeni eklenen materyal listesi
            sop_date DATE,
            description TEXT,
            embedding vector(768),
            rating DOUBLE PRECISION, -- Yeni eklenen rating
            lat DOUBLE PRECISION,
            lng DOUBLE PRECISION   -- 'lon' yerine 'lng' olarak güncellendi
        );
    """)
    
    # Indexler
    cur.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_vector ON suppliers USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_name_trgm ON suppliers USING gin (name gin_trgm_ops);")
    
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Veritabanı şeması hazırlendi.")
