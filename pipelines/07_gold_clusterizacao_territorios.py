import os
from pathlib import Path
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.cluster import KMeans
from k_means_constrained import KMeansConstrained
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from pymongo import MongoClient, UpdateOne
from services.datalake_service import datalake

def conectar_banco():
    uri = os.getenv("COSMOS_MONGO_URI") or os.getenv("COSMOS_MONGO_CONNECTION_STRING")
    if not uri:
        raise ValueError("Defina COSMOS_MONGO_URI no arquivo .env.")
    banco = os.getenv("COSMOS_DB_NAME", "bf_geosmart")
    cliente = MongoClient(uri, serverSelectionTimeoutMS=20000)
    return cliente, cliente[banco]

def carregar_dados_cosmos(db):
    print("1. Lendo Lojas e GEFINs diretamente do Cosmos DB...")
    
    # Conta quantos GEFINs estão ativos na coleção colaboradores
    k_gefins = db["colaboradores"].count_documents({"tipo_colaborador": "GEFIN", "ativo": True})
    print(f" -> Quantidade atual de GEFINs ativos: {k_gefins}")

    # Traz apenas as lojas que têm coordenadas reais
    lojas_cursor = db["lojas"].find({"geocodificado_real": True, "localizacao": {"$exists": True}})
    
    lojas_lista = []
    for loja in lojas_cursor:
        lon, lat = loja["localizacao"]["coordinates"]
        # Puxa a estatística que a Pipeline 06 acabou de gravar (ou assume 0.0 se não tiver)
        prod_media = loja.get("estatisticas", {}).get("producao_media", 0.0)
        
        lojas_lista.append({
            "cnpj_loja": str(loja["cnpj"]),
            "latitude": float(lat),
            "longitude": float(lon),
            "gefin_atual": loja.get("gefin_id"),
            "producao_media": float(prod_media)
        })

    # Remove CNPJs duplicados caso existam anomalias na base
    df_modelo = pd.DataFrame(lojas_lista).drop_duplicates(subset=["cnpj_loja"])
    
    print(f" -> Total de lojas preparadas para o modelo: {len(df_modelo)}")
    return df_modelo, k_gefins

def preparar_variaveis(df_modelo):
    print("2. Preparando variáveis (Jittering e StandardScaler apenas para Lat/Lon)...")
    rng = np.random.default_rng(42)

    df_modelo["lat_ajustada"] = df_modelo["latitude"] + rng.normal(0, 0.0001, size=len(df_modelo))
    df_modelo["lon_ajustada"] = df_modelo["longitude"] + rng.normal(0, 0.0001, size=len(df_modelo))

    scaler = StandardScaler()
    colunas = ["lat_ajustada", "lon_ajustada"]
    dados_normalizados = scaler.fit_transform(df_modelo[colunas])

    return df_modelo, dados_normalizados

def sugerir_k_ideal(dados_normalizados, k_atual):
    print("3. Testando cenários para sugerir um número mais adequado de GEFINs...")
    candidatos_k = sorted({max(10, int(k_atual * fator)) for fator in [0.5, 0.7, 0.85, 1.0, 1.15]})

    melhor_k = k_atual
    melhor_score = -1.0

    for k in candidatos_k:
        # modelo_teste = KMeans(n_clusters=k, n_init="auto", random_state=42)
        modelo_teste = KMeansConstrained(n_clusters=k,size_max=(len(dados_normalizados) // k) * 1.15, n_init="auto", random_state=42)
        rotulos = modelo_teste.fit_predict(dados_normalizados)

        score = silhouette_score(
            dados_normalizados,
            rotulos,
            sample_size=min(5000, len(dados_normalizados)),
            random_state=42,
        )
        print(f" -> Teste com K={k} | Silhueta: {score:.4f}")

        if score > melhor_score:
            melhor_score = score
            melhor_k = k

    print(f" -> Número sugerido pelo modelo: {melhor_k} GEFINs (Quadro atual: {k_atual})")
    return melhor_k

def rodar_kmeans_e_salvar(df_modelo, dados_normalizados, k_atual, k_sugerido, db):
    print(f"4. Agrupando as lojas com o total atual de GEFINs (K={k_atual})...")
    # kmeans = KMeans(n_clusters=k_atual, n_init="auto", random_state=42)
    kmeans = KMeansConstrained(n_clusters=k_atual,size_max=(len(dados_normalizados) // k_atual) * 1.15, n_init="auto", random_state=42)
    df_modelo["cluster_id"] = kmeans.fit_predict(dados_normalizados)

    print("5. Salvando o cluster_id no Cosmos DB e no Data Lake...")
    operacoes = []
    docs_backup = []
    
    for _, row in df_modelo.iterrows():
        cluster = int(row["cluster_id"])
        
        # 1. Prepara a atualização no Cosmos DB
        operacoes.append(
            UpdateOne(
                {"cnpj": row["cnpj_loja"]},
                {"$set": {"cluster_id": cluster}}
            )
        )
        
        # 2. Monta o documento para o backup no Data Lake
        docs_backup.append({
            "cnpj_loja": row["cnpj_loja"],
            "cluster_id": cluster,
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "producao_media": row["producao_media"]
        })

    # Executa as gravações no banco em blocos para não estourar os RU/s
    lote_size = 1000
    for i in range(0, len(operacoes), lote_size):
        db["lojas"].bulk_write(operacoes[i:i + lote_size])
        
    print(" -> Cosmos DB atualizado com sucesso!")

    # Faz o upload do backup para a camada Gold
    datalake.upload_json("gold", "modelagem_final/lojas_clusterizadas_gold.json", docs_backup)
    print(" -> Backup salvo no Data Lake (gold/modelagem_final/lojas_clusterizadas_gold.json).")

def main():
    load_dotenv(override=True)
    cliente, db = conectar_banco()
    
    try:
        df_modelo, k_atual = carregar_dados_cosmos(db)
        if df_modelo.empty:
            print("Aviso: Nenhuma loja encontrada para clusterizar.")
            return

        df_modelo, dados_normalizados = preparar_variaveis(df_modelo)
        k_sugerido = sugerir_k_ideal(dados_normalizados, k_atual)
        
        rodar_kmeans_e_salvar(df_modelo, dados_normalizados, k_atual, k_sugerido, db)
        print("\nPipeline 07 executada com sucesso. Os clusters estão no banco!")
        
    finally:
        cliente.close()

if __name__ == "__main__":
    main()