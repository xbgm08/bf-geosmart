from pymongo.collection import Collection

class LojaRepository:
    def __init__(self, collection: Collection):
        self.collection = collection

    def criar(self, loja_data: dict) -> str:
        resultado = self.collection.insert_one(loja_data)
        return str(resultado.inserted_id)

    def listar_com_filtros(self, query: dict, skip: int, limit: int) -> list:
        cursor = self.collection.find(query, {"_id": 0}).skip(skip).limit(limit)
        return list(cursor)

    def buscar_por_cnpj(self, cnpj: str) -> dict:
        return self.collection.find_one({"cnpj": cnpj}, {"_id": 0})

    def atualizar(self, cnpj: str, update_data: dict) -> int:
        resultado = self.collection.update_one({"cnpj": cnpj}, {"$set": update_data})
        return resultado.matched_count

    def deletar(self, cnpj: str) -> int:
        resultado = self.collection.delete_one({"cnpj": cnpj})
        return resultado.deleted_count