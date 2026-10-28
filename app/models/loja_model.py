from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class GeoJSONPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float] = Field(..., description="[longitude, latitude]")

class LojaBase(BaseModel):
    cnpj: str = Field(..., description="CNPJ da loja (apenas números)")
    razao_social: str
    nome_fantasia: Optional[str] = None
    cnae_principal: Optional[str] = None
    porte: Optional[str] = "DEMAIS"
    uf: str = Field(..., max_length=2)
    municipio: str
    endereco_bairro: Optional[str] = None
    endereco_logradouro: Optional[str] = None
    endereco_cep: Optional[str] = None
    gefin_id: Optional[str] = None
    tier_loja: Optional[str] = "BRONZE"
    localizacao: Optional[GeoJSONPoint] = None

class LojaCreate(LojaBase):
    pass

class LojaUpdate(BaseModel):
    razao_social: Optional[str] = None
    nome_fantasia: Optional[str] = None
    cnae_principal: Optional[str] = None
    porte: Optional[str] = None
    uf: Optional[str] = Field(None, max_length=2)
    municipio: Optional[str] = None
    endereco_bairro: Optional[str] = None
    endereco_logradouro: Optional[str] = None
    endereco_cep: Optional[str] = None
    gefin_id: Optional[str] = None
    tier_loja: Optional[str] = None
    localizacao: Optional[GeoJSONPoint] = None

class LojaResponse(LojaBase):
    cluster_id: Optional[int] = None
    estatisticas: Optional[Dict[str, Any]] = None
    historico_share: Optional[List[Dict[str, Any]]] = []