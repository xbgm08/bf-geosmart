from typing import Optional
from fastapi import HTTPException
from app.repositories.loja_repository import LojaRepository
from app.models.loja_model import LojaCreate, LojaUpdate

class LojaService:
    def __init__(self, repository: LojaRepository):
        self.repository = repository

    def registrar_loja(self, loja: LojaCreate) -> dict:
        if self.repository.buscar_por_cnpj(loja.cnpj):
            raise HTTPException(status_code=400, detail="CNPJ já registado no sistema.")
        
        loja_dict = loja.model_dump(exclude_none=True)
        loja_dict["_id"] = loja_dict["cnpj"]
        loja_dict["endereco_uf"] = loja_dict.pop("uf").upper()
        loja_dict["endereco_municipio"] = loja_dict.pop("municipio")
        if "cnae_principal" in loja_dict:
            loja_dict["cnae_fiscal"] = loja_dict.pop("cnae_principal")
        if "localizacao" in loja_dict:
            loja_dict["geocodificado_real"] = True

        loja_dict["historico_share"] = []

        id_doc = self.repository.criar(loja_dict)
        return {"mensagem": "Loja registada com sucesso", "id_documento": id_doc}

    def consultar_lojas(self, uf: Optional[str] = None, tier: Optional[str] = None, gefin_id: Optional[str] = None, busca: Optional[str] = None, skip: int = 0, limit: int = 20,) -> list:
        query = {}
        if uf:
            query["endereco_uf"] = uf.upper()
        if tier:
            query["tier_loja"] = tier.upper()
        if gefin_id:
            query["gefin_id"] = gefin_id
        if busca:
            termo = busca.strip()
            query["$or"] = [
                {"cnpj": {"$regex": termo, "$options": "i"}},
                {"razao_social": {"$regex": termo, "$options": "i"}},
                {"nome_fantasia": {"$regex": termo, "$options": "i"}},
                {"endereco_municipio": {"$regex": termo, "$options": "i"}},
            ]
        return self.repository.listar_com_filtros(query, skip, limit)

    def buscar_loja_unica(self, cnpj: str) -> dict:
        loja = self.repository.buscar_por_cnpj(cnpj)
        if not loja:
            raise HTTPException(status_code=404, detail="Loja não encontrada.")
        return loja

    def modificar_loja(self, cnpj: str, loja_update: LojaUpdate) -> dict:
        update_data = loja_update.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="Nenhum dado fornecido para atualização.")

        if "uf" in update_data and update_data["uf"]:
            update_data["endereco_uf"] = update_data.pop("uf").upper()
        if "municipio" in update_data and update_data["municipio"]:
            update_data["endereco_municipio"] = update_data.pop("municipio")
        if "cnae_principal" in update_data and update_data["cnae_principal"]:
            update_data["cnae_fiscal"] = update_data.pop("cnae_principal")
        if "localizacao" in update_data and update_data["localizacao"]:
            update_data["geocodificado_real"] = True

        matched = self.repository.atualizar(cnpj, update_data)
        if matched == 0:
            raise HTTPException(status_code=404, detail="Loja não encontrada.")
        return {"mensagem": "Loja atualizada com sucesso"}

    def remover_loja(self, cnpj: str):
        deleted = self.repository.deletar(cnpj)
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Loja não encontrada.")