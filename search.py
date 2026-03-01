import logging
import requests
from langchain_ollama import OllamaEmbeddings
from database import get_connection

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class HybridSearchEngine:
    def __init__(self):
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")

    def geocode_city(self, city: str):
        """
        Converts a city name to lat/lng using the Nominatim API.
        Used only on the backend.
        """
        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "Aria-Sourcing-Agent/1.0"}
        params = {
            "q": city,
            "format": "json",
            "limit": 1
        }
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
            else:
                log.warning(f"Geocoding failed for city: {city}")
                return None
        except Exception as e:
            log.error(f"Geocoding error for {city}: {e}")
            return None

    def search(self, query: str, certs: list = None, regs: list = None, near_city: str = None, 
               radius_km: float = None, countries: list = None, strict_mode: bool = True, top_k: int = 5):
        """
        Advanced hybrid search:
        - Vector similarity (pgvector)
        - Strict/Soft filtering (certifications, regulatory)
        - Geospatial filtering and distance-based scoring (ST_DWithin, ST_Distance)
        - Country-based filtering
        - Trigram-based deduplication (pg_trgm)
        """
        query_vector = self.embeddings.embed_query(query)
        
        center_lat, center_lng = None, None
        radius_meters = None
        if near_city:
            coords = self.geocode_city(near_city)
            if coords:
                center_lat, center_lng = coords
                if radius_km:
                    radius_meters = radius_km * 1000

        conn = get_connection()
        cur = conn.cursor()
        
        certs = certs or []
        regs = regs or []
        countries = countries or None # psycopg2 handle None as NULL
        
        # Complex SQL query: Filtering, Scoring, and Deduplication
        sql = """
        WITH filtered_suppliers AS (
            SELECT 
                supplier_id, name, certifications, regulatory, materials, rating, description, city, country, lat, lng, location,
                (1.0 - (embedding <=> %s::vector)) as vector_similarity
            FROM suppliers
            WHERE 
                (NOT %s OR (%s::text[] <@ certifications)) AND -- strict cert filter
                (NOT %s OR (%s::text[] <@ regulatory)) AND     -- strict reg filter
                (%s::text[] IS NULL OR country = ANY(%s)) AND  -- country filter
                (%s::float IS NULL OR ST_DWithin(location, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)) -- radius filter
        ),
        scored_suppliers AS (
            SELECT 
                *,
                CASE 
                    WHEN %s::float IS NOT NULL AND %s::float IS NOT NULL AND %s::float IS NOT NULL THEN
                        GREATEST(0.0, 1.0 - (ST_Distance(location, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) / %s)) * 0.3
                    ELSE 0.0
                END as proximity_bonus,
                CASE 
                    WHEN NOT %s THEN 
                        (SELECT count(distinct c) FROM unnest(certifications) as c WHERE c = ANY(%s)) * 0.2 +
                        (SELECT count(distinct r) FROM unnest(regulatory) as r WHERE r = ANY(%s)) * 0.2
                    ELSE 0.0
                END as match_bonus
            FROM filtered_suppliers
        ),
        final_scored AS (
            SELECT 
                *,
                (vector_similarity + proximity_bonus + match_bonus) as total_suitability,
                CASE 
                    WHEN %s::float IS NOT NULL AND %s::float IS NOT NULL THEN 
                         ST_Distance(location, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) / 1000.0
                    ELSE NULL
                END as distance_km
            FROM scored_suppliers
        ),
        deduplicated AS (
            -- Deduplicates entries with similarity > 0.75, keeping the one with the highest score
            -- DISTINCT ON is only good for exact matches, so we use fuzzy logic (NOT EXISTS)
            SELECT * FROM final_scored s1
            WHERE NOT EXISTS (
                SELECT 1 FROM final_scored s2
                WHERE s2.total_suitability > s1.total_suitability
                AND (s1.name = s2.name OR similarity(s1.name, s2.name) > 0.75)
                AND s1.supplier_id <> s2.supplier_id
            )
        )
        SELECT * FROM (
            SELECT DISTINCT ON (name) *
            FROM deduplicated
            ORDER BY name, total_suitability DESC
        ) sub
        ORDER BY total_suitability DESC
        LIMIT %s;
        """
        
        # Prepare parameters
        params = (
            query_vector, 
            strict_mode, certs, 
            strict_mode, regs, 
            countries, countries,
            radius_meters, center_lng, center_lat, radius_meters,
            # proximity_bonus calculation params
            center_lng, center_lat, radius_meters, center_lng, center_lat, radius_meters,
            # match_bonus params
            strict_mode, certs, regs,
            # distance_km params
            center_lng, center_lat, center_lng, center_lat,
            top_k
        )
        
        try:
            cur.execute(sql, params)
            results = cur.fetchall()
            
            # Column names from cursor description
            columns = [desc[0] for desc in cur.description]
            
            formatted_results = []
            for res in results:
                row = dict(zip(columns, res))
                
                formatted_results.append({
                    "supplier_id": row["supplier_id"],
                    "name": row["name"],
                    "certifications": row["certifications"],
                    "regulatory_compliance": row["regulatory"],
                    "materials": row["materials"],
                    "rating": row["rating"],
                    "country": row["country"],
                    "city": row["city"],
                    "lat": row["lat"],
                    "lng": row["lng"],
                    "distance_km": float(row["distance_km"]) if row["distance_km"] is not None else None,
                    "description_preview": (row["description"][:200] + "...") if row["description"] else "",
                    "scores": {
                        "vector_similarity": round(float(row["vector_similarity"]), 4),
                        "proximity_bonus": round(float(row["proximity_bonus"]), 4),
                        "match_bonus": round(float(row.get("match_bonus", 0)), 4),
                        "total_suitability": round(float(row["total_suitability"]), 4)
                    }
                })
        except Exception as e:
            log.error(f"Search query failed: {e}")
            formatted_results = []
        finally:
            cur.close()
            conn.close()
            
        return {
            "results": formatted_results,
            "center_coords": [center_lat, center_lng] if center_lat and center_lng else None
        }

# For testing
if __name__ == "__main__":
    engine = HybridSearchEngine()
    # Example search
    search_data = engine.search("high pressure aluminum casting", near_city="Mexico City", radius_km=500)
    for r in search_data["results"]:
        print(f"[{r['scores']['total_suitability']}] {r['name']} ({r['country']}) - {r['distance_km']} km")

# For testing
if __name__ == "__main__":
    engine = HybridSearchEngine()
    # Example search
    search_data = engine.search("high pressure aluminum casting", certs=["ISO 9001"])
    for r in search_data["results"]:
        print(f"[{r['scores']['total_suitability']}] {r['name']} - {r['scores']}")
