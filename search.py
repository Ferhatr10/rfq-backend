import logging
from langchain_ollama import OllamaEmbeddings
from database import get_connection

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class HybridSearchEngine:
    def __init__(self):
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")

    def search(self, query: str, certs: list = None, regs: list = None, strict_mode: bool = True, top_k: int = 5):
        """
        Hibrit arama yapar:
        - strict_mode=True: Kriterlere uymayanları eler (Hard Filter).
        - strict_mode=False: Herkesi getirir, kriterlere uyanlara bonus puan verir (Scoring).
        """
        query_vector = self.embeddings.embed_query(query)
        
        conn = get_connection()
        cur = conn.cursor()
        
        certs = certs or []
        regs = regs or []
        
        if strict_mode:
            # SERT FİLTRELEME: Kriterlere uymayanlar elenir
            sql = """
            SELECT 
                supplier_id, name, certifications, regulatory, materials, rating, description,
                (1.0 - (embedding <=> %s::vector)) as vector_score,
                0.0 as match_bonus
            FROM suppliers
            WHERE 
                (%s::text[] <@ certifications) AND
                (%s::text[] <@ regulatory)
            ORDER BY (1.0 - (embedding <=> %s::vector)) DESC
            LIMIT %s;
            """
            params = (query_vector, certs, regs, query_vector, top_k)
        else:
            # PUANLAMA MODU: Herkes gelir, uyanlar üste çıkar
            sql = """
            SELECT 
                supplier_id, name, certifications, regulatory, materials, rating, description,
                (1.0 - (embedding <=> %s::vector)) as vector_score,
                (
                    (SELECT count(*) FROM unnest(certifications) as c WHERE c = ANY(%s)) * 0.2 +
                    (SELECT count(*) FROM unnest(regulatory) as r WHERE r = ANY(%s)) * 0.2
                ) as match_bonus
            FROM suppliers
            ORDER BY (1.0 - (embedding <=> %s::vector)) + 
                     ((SELECT count(*) FROM unnest(certifications) as c WHERE c = ANY(%s)) * 0.2) +
                     ((SELECT count(*) FROM unnest(regulatory) as r WHERE r = ANY(%s)) * 0.2) DESC
            LIMIT %s;
            """
            params = (query_vector, certs, regs, query_vector, certs, regs, top_k)
        
        cur.execute(sql, params)
        results = cur.fetchall()
        
        formatted_results = []
        for res in results:
            s_id, name, r_certs, r_regs, r_mats, rating, desc, v_score, m_bonus = res
            
            # Type casting to prevent float + Decimal mismatch
            v_score = float(v_score) if v_score is not None else 0.0
            m_bonus = float(m_bonus) if m_bonus is not None else 0.0
            
            formatted_results.append({
                "supplier_id": s_id,
                "name": name,
                "certifications": r_certs,
                "regulatory_compliance": r_regs,
                "materials": r_mats,
                "rating": rating,
                "description_preview": desc[:200] + "...",
                "scores": {
                    "vector_similarity": round(v_score, 4),
                    "match_bonus": round(m_bonus, 2),
                    "total_suitability": round(v_score + m_bonus, 4)
                }
            })
            
        cur.close()
        conn.close()
        return formatted_results

# Test amaçlı
if __name__ == "__main__":
    engine = HybridSearchEngine()
    # Örnek arama
    test_results = engine.search("high pressure aluminum casting", certs=["ISO 9001"])
    for r in test_results:
        print(f"[{r['scores']['total_suitability']}] {r['name']} - {r['scores']}")
