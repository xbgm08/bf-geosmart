import os
import time
import warnings
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import BulkWriteError, OperationFailure

warnings.filterwarnings("ignore", message="You appear to be connected to a CosmosDB cluster")

load_dotenv(override=True)

class CosmosDatabaseService:
    def __init__(self):
        self.uri = os.getenv("COSMOS_MONGO_URI") or os.getenv("COSMOS_MONGO_CONNECTION_STRING")
        self.db_name = os.getenv("COSMOS_DB_NAME", "bf_geosmart")
        self._client = None
        self._db = None

    def conectar(self):
        """Retorna a tupla (cliente, db) pronta para uso nas pipelines."""
        if not self.uri:
            raise ValueError("A variável COSMOS_MONGO_URI não foi encontrada no arquivo .env.")

        if self._client is None:
            self._client = MongoClient(self.uri, serverSelectionTimeoutMS=20000)
            self._db = self._client[self.db_name]

        return self._client, self._db

    def obter_db(self):
        """Retorna apenas o objeto do banco de dados (ideal para os Routers da FastAPI)."""
        _, db = self.conectar()
        return db

    def obter_colecao(self, nome_colecao: str):
        """Atalho para pegar uma coleção específica."""
        db = self.obter_db()
        return db[nome_colecao]

    def gravar_em_lotes(self, nome_colecao: str, operacoes: list, tamanho_lote: int = 1000):
        """
        Executa bulk_write em lotes tratando automaticamente o limite de RU/s
        """
        if not operacoes:
            return

        colecao = self.obter_colecao(nome_colecao)
        total = len(operacoes)

        for i in range(0, total, tamanho_lote):
            lote = operacoes[i : i + tamanho_lote]
            while lote:
                try:
                    colecao.bulk_write(lote, ordered=False)
                    break
                except BulkWriteError as erro_bulk:
                    erros = erro_bulk.details.get("writeErrors", [])
                    indices_16500 = [e["index"] for e in erros if e.get("code") == 16500]
                    if indices_16500:
                        lote = [lote[idx] for idx in indices_16500]
                        time.sleep(1.5)
                    else:
                        break
                except OperationFailure as erro_op:
                    if erro_op.code == 16500 or "16500" in str(erro_op):
                        time.sleep(1.5)
                    else:
                        raise

    def fechar(self):
        """Fecha a conexão com o banco quando necessário."""
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None


cosmos_db = CosmosDatabaseService()

def conectar_banco():
    return cosmos_db.conectar()