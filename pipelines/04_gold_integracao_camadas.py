import os
import time
from pathlib import Path
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
                # Separa apenas os documentos que falharam por limite de velocidade (16500)
                indices_16500 = [e["index"] for e in erros if e.get("code") == 16500]
                erros_fatais = [e for e in erros if e.get("code") not in (16500, 11000)]

                if erros_fatais:
                    raise bwe

                if indices_16500:
                    # Reenvia APENAS os documentos que ainda não entraram por limite de RU/s
                    lote = [lote[idx] for idx in indices_16500]
                    time.sleep(1.5)
                else:
                    # Se só houve erro 11000 (duplicata), o ordered=False já inseriu todos os inéditos
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

    client = MongoClient(uri_mongo)
    db = client[db_name]

    print("1. A extrair dados do Data Lake (Camada Silver - Gerador v2)...")
    colaboradores = datalake.download_json("silver", "dados_sinteticos/colaboradores.json")
    propostas = datalake.download_json("silver", "dados_sinteticos/propostas.json")
    metas_loja = datalake.download_json("silver", "dados_sinteticos/metas_loja.json")
    historico_share = datalake.download_json("silver", "dados_sinteticos/historico_share.json")

    # Remove metas duplicadas geradas por CNPJs repetidos na coleção de lojas
    total_metas_bruto = len(metas_loja)
    metas_loja = list({m["_id"]: m for m in metas_loja}.values())
    if len(metas_loja) < total_metas_bruto:
        print(f" -> Metas desduplicadas por _id: de {total_metas_bruto} para {len(metas_loja)}")

    print("\n2. A recuperar as Lojas já geocodificadas do Cosmos DB (Intactas)...")
    lojas_gold = list(db['lojas'].find({}, {'_id': 0}))
    print(f" -> Lojas lidas do Cosmos DB: {len(lojas_gold)}")

    print("\n3. A guardar as bases enriquecidas finais na camada GOLD...")
    datalake.upload_json("gold", "modelagem_final/lojas_gold.json", lojas_gold)
    datalake.upload_json("gold", "modelagem_final/colaboradores_gold.json", colaboradores)
    datalake.upload_json("gold", "modelagem_final/propostas_gold.json", propostas)
    datalake.upload_json("gold", "modelagem_final/metas_loja_gold.json", metas_loja)
    datalake.upload_json("gold", "modelagem_final/historico_share_gold.json", historico_share)

    print("\n4. A atualizar dados no Azure Cosmos DB (Preservando a coleção 'lojas')...")
    for col in ['propostas', 'colaboradores', 'metas_loja']:
        db[col].drop()

    inserir_em_lotes(db['colaboradores'], colaboradores, tamanho_lote=500, nome_colecao="Colaboradores")
    print(f" -> Colaboradores carregados com sucesso: {db['colaboradores'].count_documents({})}")

    inserir_em_lotes(db['metas_loja'], metas_loja, tamanho_lote=1000, nome_colecao="Metas")
    print(f" -> Metas carregadas com sucesso: {db['metas_loja'].count_documents({})}")

    inserir_em_lotes(db['propostas'], propostas, tamanho_lote=1000, nome_colecao="Propostas")
    print(f" -> Propostas carregadas com sucesso: {db['propostas'].count_documents({})}")

    client.close()
    print("\nIntegração Gold concluída!")

if __name__ == "__main__":
    main()