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
        loja_dict['historico_share'] = []
        
        id_doc = self.repository.criar(loja_dict)
        return {"mensagem": "Loja registada com sucesso", "id_documento": id_doc}

    def consultar_lojas(self, uf: str, tier: str, skip: int, limit: int) -> list:
        query = {}
        if uf: query["uf"] = uf.upper()
        if tier: query["tier_loja"] = tier.upper()
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
            
        matched = self.repository.atualizar(cnpj, update_data)
        if matched == 0:
            raise HTTPException(status_code=404, detail="Loja não encontrada.")
        return {"mensagem": "Loja atualizada com sucesso"}

    def remover_loja(self, cnpj: str):
        deleted = self.repository.deletar(cnpj)
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Loja não encontrada.")