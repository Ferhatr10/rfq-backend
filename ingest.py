import csv
import json
import sqlite3
import sys
import logging
import ast
import os
from langchain_ollama import OllamaEmbeddings
from database import get_connection, init_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def process_records(records):
    """
    Common data processing and DB save logic.
    Accepts 'list of dict' structure from both CSV and JSON sources.
    """
    init_db()
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    
    conn = get_connection()
    cur = conn.cursor()
    
    count = 0
    for row in records:
        s_id = row.get('supplier_id')
        name = row.get('company_name') or row.get('name') or 'Unknown Supplier'
        
        # Safely parse list-formatted data (['A', 'B'])
        def parse_list(val):
            if not val: return []
            if isinstance(val, list): return val
            try:
                if isinstance(val, str) and '[' in val:
                    return ast.literal_eval(val)
                return [i.strip() for i in val.split(',')]
            except:
                return []

        capabilities = parse_list(row.get('capabilities'))
        materials = parse_list(row.get('materials'))
        certs = parse_list(row.get('certifications'))
        regu = parse_list(row.get('regulatory_compliance'))
        
        # Description for embedding (Search Engine uses this)
        full_desc = f"Capabilities: {', '.join(capabilities)}. Materials: {', '.join(materials)}."
        
        # Missing data check and warnings
        if not capabilities and not materials:
            log.warning(f"(!) {name}: No capability or material data. May not appear in vector search.")
        
        sop_date = row.get('sop_date')
        try:
            rating = float(row.get('rating')) if row.get('rating') else 0.0
        except:
            rating = 0.0
        
        try:
            lat = float(row.get('lat')) if row.get('lat') is not None else None
            lng = float(row.get('lng')) if row.get('lng') is not None else None
            if lat is None or lng is None:
                log.warning(f"(!) {name}: Missing coordinates. Will not appear in map searches.")
        except:
            lat, lng = None, None

        city = row.get('city')
        country = row.get('country')
        
        log.info(f"Generating vector ({count+1}): {name}")
        vector = embeddings.embed_query(full_desc)
        
        cur.execute("""
            INSERT INTO suppliers (supplier_id, name, certifications, regulatory, materials, sop_date, description, embedding, rating, lat, lng, city, country)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (s_id, name, certs, regu, materials, sop_date, full_desc, vector, rating, lat, lng, city, country))
        
        count += 1
        if count % 10 == 0:
            conn.commit()
            log.info(f"{count} records processed...")
                
    conn.commit()
    cur.close()
    conn.close()
    log.info(f"Ingestion completed. Total {count} records.")

def ingest_csv(path):
    log.info(f"CSV Ingestion: {path}")
    with open(path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        process_records(list(reader))

def ingest_json(path):
    log.info(f"JSON Ingestion: {path}")
    with open(path, mode='r', encoding='utf-8') as f:
        data = json.load(f)
        if isinstance(data, list):
            process_records(data)
        else:
            process_records([data])

def ingest_sqlite(path, table_name="suppliers"):
    """
    Reads data from a SQLite file.
    Defaults to the 'suppliers' table.
    """
    log.info(f"SQLite Ingestion: {path} (Table: {table_name})")
    try:
        conn = sqlite3.connect(path)
        # Set row_factory to get column names as dict
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute(f"SELECT * FROM {table_name}")
        rows = [dict(row) for row in cur.fetchall()]
        
        process_records(rows)
        conn.close()
    except Exception as e:
        log.error(f"SQLite error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        sys.exit(1)

    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.csv':
        ingest_csv(file_path)
    elif ext == '.json':
        ingest_json(file_path)
    elif ext in ['.db', '.sqlite', '.sqlite3']:
        # Default table name: suppliers
        ingest_sqlite(file_path)
    else:
        print("Error: Only .csv, .json, or .db/.sqlite files are supported.")
