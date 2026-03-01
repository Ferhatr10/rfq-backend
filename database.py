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
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    
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
            lng DOUBLE PRECISION,   -- 'lon' yerine 'lng' olarak güncellendi
            city TEXT,
            country TEXT,
            location GEOGRAPHY(POINT, 4326)
        );
    """)

    # Mevcut tablolar için yeni kolonlar ekle (Idempotent)
    cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS city TEXT;")
    cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS country TEXT;")
    cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS location GEOGRAPHY(POINT, 4326);")

    # Mevcut verileri güncelle: lat/lng -> location
    cur.execute("""
        UPDATE suppliers 
        SET location = ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
        WHERE location IS NULL AND lat IS NOT NULL AND lng IS NOT NULL;
    """)
    
    # Indexler
    cur.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_vector ON suppliers USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_name_trgm ON suppliers USING gin (name gin_trgm_ops);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_location ON suppliers USING gist (location);")

    # Trigger Fonksiyonu: lat/lng değiştiğinde location'ı güncelle
    cur.execute("""
        CREATE OR REPLACE FUNCTION update_supplier_location()
        RETURNS TRIGGER AS $$
        BEGIN
            IF (NEW.lat IS NOT NULL AND NEW.lng IS NOT NULL) THEN
                IF (OLD IS NULL) OR (OLD.lat IS DISTINCT FROM NEW.lat OR OLD.lng IS DISTINCT FROM NEW.lng) THEN
                    NEW.location := ST_SetSRID(ST_MakePoint(NEW.lng, NEW.lat), 4326)::geography;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Trigger Oluştur
    cur.execute("""
        DROP TRIGGER IF EXISTS trg_update_supplier_location ON suppliers;
        CREATE TRIGGER trg_update_supplier_location
        BEFORE INSERT OR UPDATE ON suppliers
        FOR EACH ROW EXECUTE FUNCTION update_supplier_location();
    """)
    
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Veritabanı şeması hazırlendi.")
