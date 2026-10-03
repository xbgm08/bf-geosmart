from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class GeoJSONPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float] = Field(..., description="[longitude, latitude]")

class LojaBase(BaseModel):
    cnpj: str = Field(..., description="CNPJ da loja (apenas números)")
    razao_social: str
    cnae_principal: str
    uf: str = Field(..., max_length=2)
    municipio: str
    gefin_id: Optional[str] = None
    tier_loja: Optional[str] = "BRONZE"
    localizacao: Optional[GeoJSONPoint] = None

class LojaCreate(LojaBase):
    pass

class LojaUpdate(BaseModel):
    razao_social: Optional[str] = None
    cnae_principal: Optional[str] = None
    uf: Optional[str] = Field(None, max_length=2)
    municipio: Optional[str] = None
    gefin_id: Optional[str] = None
    tier_loja: Optional[str] = None
    localizacao: Optional[GeoJSONPoint] = None

class LojaResponse(LojaBase):
    historico_share: Optional[List[Dict[str, Any]]] = []