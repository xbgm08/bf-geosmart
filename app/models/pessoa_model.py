from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class HierarquiaRef(BaseModel):
    sucom_responsavel_id: Optional[str] = None
    gecom_responsavel_id: Optional[str] = None

class PessoaOut(BaseModel):
    id: str
    tipo_colaborador: str
    matricula: str
    nome: str
    email: Optional[str] = None
    cargo: Optional[str] = None
    hierarquia: Optional[HierarquiaRef] = None
    base_operacional: Optional[Dict[str, Any]] = None
    ativo: bool = True