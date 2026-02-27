from typing import List, Optional, Union
from pydantic import BaseModel, Field

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

class RFQField(BaseModel):
    value: Optional[Union[str, List[str]]] = Field(None, description="The extracted value for the field")
    confidence: int = Field(0, ge=0, le=100, description="Confidence score from 0 to 100")

class RFQResponse(BaseModel):
    component_name: RFQField = Field(..., description=RFQ_FIELDS["component_name"])
    manufacturing_process: RFQField = Field(..., description=RFQ_FIELDS["manufacturing_process"])
    material_spec: RFQField = Field(..., description=RFQ_FIELDS["material_spec"])
    certifications: RFQField = Field(..., description=RFQ_FIELDS["certifications"])
    regulatory: RFQField = Field(..., description=RFQ_FIELDS["regulatory"])
    industry: RFQField = Field(..., description=RFQ_FIELDS["industry"])
    surface_treatment: RFQField = Field(..., description=RFQ_FIELDS["surface_treatment"])
    lifetime: RFQField = Field(..., description=RFQ_FIELDS["lifetime"])
    sop_date: RFQField = Field(..., description=RFQ_FIELDS["sop_date"])
    weight: RFQField = Field(..., description=RFQ_FIELDS["weight"])
    operating_conditions: RFQField = Field(..., description=RFQ_FIELDS["operating_conditions"])