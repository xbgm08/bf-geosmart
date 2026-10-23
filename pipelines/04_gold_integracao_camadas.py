import os
import time
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import BulkWriteError, OperationFailure
from tqdm import tqdm
from services.datalake_service import datalake

def inserir_em_lotes(colecao, documentos, tamanho_lote=1000, nome_colecao="Documentos"):
    """Insere grandes volumes no Cosmos DB tratando limite de RU/s (16500) e chaves duplicadas (11000)."""
    if not documentos:
        return

    total = len(documentos)
    for i in tqdm(range(0, total, tamanho_lote), desc=f"Inserindo {nome_colecao}"):
        lote = documentos[i : i + tamanho_lote]
        while lote:
            try:
                colecao.insert_many(lote, ordered=False)
                break
            except BulkWriteError as bwe:
                erros = bwe.details.get("writeErrors", [])
                indices_16500 = [e["index"] for e in erros if e.get("code") == 16500]
                erros_fatais = [e for e in erros if e.get("code") not in (16500, 11000)]

                if erros_fatais:
                    raise bwe

                if indices_16500:
                    lote = [lote[idx] for idx in indices_16500]
                    time.sleep(1.5)
                else:
                    break
            except OperationFailure as erro:
                if erro.code == 16500 or "16500" in str(erro):
                    time.sleep(1.5)
                else:
                    raise

def main():
    load_dotenv(override=True)
    uri_mongo = os.getenv("COSMOS_MONGO_URI")
    db_name = os.getenv("COSMOS_DB_NAME", "bf_geosmart")

    client = MongoClient(uri_mongo, serverSelectionTimeoutMS=20000)
    db = client[db_name]

    print("1. Extraindo bases regionalizadas do Data Lake (Camada Silver)...")
    lojas_silver = datalake.download_json("silver", "dados_sinteticos/lojas_enriquecidas.json")
    colaboradores = datalake.download_json("silver", "dados_sinteticos/colaboradores.json")
    propostas = datalake.download_json("silver", "dados_sinteticos/propostas.json")
    metas_loja = datalake.download_json("silver", "dados_sinteticos/metas_loja.json")
    historico_share = datalake.download_json("silver", "dados_sinteticos/historico_share.json")

    metas_loja = list({m["_id"]: m for m in metas_loja}.values())

    print("\n2. Preparando coleção 'lojas' com chave única (_id = cnpj)...")
    coordenadas_existentes = {}
    for doc in db["lojas"].find(
        {"localizacao": {"$exists": True}},
        {"cnpj": 1, "localizacao": 1, "geocodificado_real": 1, "precisao_geocodificacao": 1}
    ):
        coordenadas_existentes[doc["cnpj"]] = doc

    lojas_gold = []
    for loja in lojas_silver:
        cnpj = loja["cnpj"]
        loja["_id"] = cnpj  # Chave primária única por CNPJ no Cosmos DB
        if cnpj in coordenadas_existentes:
            antigo = coordenadas_existentes[cnpj]
            loja["localizacao"] = antigo.get("localizacao")
            loja["geocodificado_real"] = antigo.get("geocodificado_real", True)
            if "precisao_geocodificacao" in antigo:
                loja["precisao_geocodificacao"] = antigo["precisao_geocodificacao"]
        lojas_gold.append(loja)

    print("\n3. Guardando bases finais na camada GOLD do Data Lake...")
    datalake.upload_json("gold", "modelagem_final/lojas_gold.json", lojas_gold)
    datalake.upload_json("gold", "modelagem_final/colaboradores_gold.json", colaboradores)
    datalake.upload_json("gold", "modelagem_final/propostas_gold.json", propostas)
    datalake.upload_json("gold", "modelagem_final/metas_loja_gold.json", metas_loja)
    datalake.upload_json("gold", "modelagem_final/historico_share_gold.json", historico_share)

    print("\n4. Recarregando coleções no Azure Cosmos DB...")
    for col in ["lojas", "propostas", "colaboradores", "metas_loja"]:
        db[col].drop()

    inserir_em_lotes(db["lojas"], lojas_gold, tamanho_lote=1000, nome_colecao="Lojas")
    print(f" -> Lojas carregadas com sucesso: {db['lojas'].count_documents({})}")

    inserir_em_lotes(db["colaboradores"], colaboradores, tamanho_lote=500, nome_colecao="Colaboradores")
    print(f" -> Colaboradores carregados com sucesso: {db['colaboradores'].count_documents({})}")

    inserir_em_lotes(db["metas_loja"], metas_loja, tamanho_lote=1000, nome_colecao="Metas")
    print(f" -> Metas carregadas com sucesso: {db['metas_loja'].count_documents({})}")

    inserir_em_lotes(db["propostas"], propostas, tamanho_lote=1000, nome_colecao="Propostas")
    print(f" -> Propostas carregadas com sucesso: {db['propostas'].count_documents({})}")

    client.close()
    print("\nIntegração Gold concluída!")

if __name__ == "__main__":
    main()