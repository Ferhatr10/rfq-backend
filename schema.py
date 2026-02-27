# ─────────────────────────────────────────────
# RFQ ŞEMASI — buraya kendi alanlarını ekle
# Her alan için: "alan_adi": "açıklama"
# ─────────────────────────────────────────────

RFQ_FIELDS = {
    "component_name": "Name of the component or part being requested",
    "manufacturing_process": "Manufacturing process required (e.g. CNC machining, casting, forging, injection molding)",
    "material_spec": "Material specification or grade (e.g. SS316L, Al6061-T6, ABS)",
    "certifications": "Required certifications as a list (e.g. ISO 9001, IATF 16949, AS9100)",
    "regulatory": "Regulatory compliance requirements as a list (e.g. RoHS, REACH, FDA)",
    "industry": "Target industry (e.g. Automotive, Aerospace, Medical, Electronics)",
    "surface_treatment": "Surface treatment or finish required (e.g. anodizing, powder coating, zinc plating)",
    "lifetime": "Expected product lifetime or durability requirement (e.g. 10 years, 1M cycles)",
    "sop_date": "Start of production date (SOP) in YYYY-MM-DD format",
    "weight": "Target or maximum weight of the component including unit (e.g. 250g, 1.5kg)",
    "operating_conditions": "Operating environment and conditions (e.g. temperature range, humidity, pressure)",
}

# Beklenen JSON çıktısı:
# {
#   "component_name": {"value": "Bracket Assembly", "confidence": 95},
#   "manufacturing_process": {"value": "CNC Machining", "confidence": 90},
#   "material_spec": {"value": "SS316L", "confidence": 85},
#   "certifications": {"value": ["ISO 9001", "IATF 16949"], "confidence": 80},
#   "regulatory": {"value": ["RoHS", "REACH"], "confidence": 75},
#   "industry": {"value": "Automotive", "confidence": 95},
#   "surface_treatment": {"value": "Zinc plating", "confidence": 70},
#   "lifetime": {"value": "10 years", "confidence": 60},
#   "sop_date": {"value": "2025-06-01", "confidence": 80},
#   "weight": {"value": "450g", "confidence": 65},
#   "operating_conditions": {"value": "-40°C to +85°C", "confidence": 75}
# }