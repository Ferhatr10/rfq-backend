import os
import psycopg2
from psycopg2.extras import execute_values
import numpy as np

# DB Connection settings (internal)
# When running on the server, omitting host/port connects via Unix Socket.
# However, due to possible permission issues, we use localhost + password.
DB_CONFIG = {
    "dbname": "rfq_db",
    "user": "postgres",
    "password": os.getenv("PGPASSWORD", "postgres"),
    "host": os.getenv("DB_HOST", "localhost")
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    """Checks/creates tables and extensions on startup."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Extensions are already in start.sh but adding them here as a safety net
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            supplier_id TEXT, -- SUP-1000 format
            name TEXT NOT NULL,
            certifications TEXT[],
            regulatory TEXT[],
            materials TEXT[],   -- Material list
            sop_date DATE,
            description TEXT,
            embedding vector(768),
            rating DOUBLE PRECISION, -- Supplier rating
            lat DOUBLE PRECISION,
            lng DOUBLE PRECISION,   -- Renamed from 'lon' to 'lng'
            city TEXT,
            country TEXT,
            location GEOGRAPHY(POINT, 4326)
        );
    """)

    # Add new columns for existing tables (Idempotent)
    cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS city TEXT;")
    cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS country TEXT;")
    cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS location GEOGRAPHY(POINT, 4326);")

    # Update existing records: lat/lng -> location
    cur.execute("""
        UPDATE suppliers 
        SET location = ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
        WHERE location IS NULL AND lat IS NOT NULL AND lng IS NOT NULL;
    """)
    
    # Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_vector ON suppliers USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_name_trgm ON suppliers USING gin (name gin_trgm_ops);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_location ON suppliers USING gist (location);")

    # Trigger Function: Update location when lat/lng changes
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

    # Create Trigger
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
    print("Database schema initialized.")
