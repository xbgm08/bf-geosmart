import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from pymongo import UpdateOne
from services.datalake_service import datalake
from services.database import cosmos_db

FATOR_TETO = 1.15

def conectar_banco():
    return cosmos_db.conectar()

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
        prod_media = loja.get("estatisticas", {}).get("producao_media", 0.0)

        lojas_lista.append({
            "cnpj_loja": str(loja["cnpj"]),
            "uf": str(loja.get("endereco_uf", "SP")).strip().upper(),
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
        modelo_teste = KMeans(n_clusters=k, n_init="auto", random_state=42)
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


def agrupar_com_limite(coordenadas, quantidade_grupos, fator_teto=FATOR_TETO):
    """
    Usa o KMeans do scikit-learn e garante que nenhum cluster ultrapasse o teto:
    teto = (total_pontos / quantidade_grupos) * peso_teto
    """
    total_pontos = len(coordenadas)
    if quantidade_grupos <= 1 or total_pontos <= 1:
        return [0] * total_pontos, coordenadas.mean(axis=0, keepdims=True), total_pontos

    if quantidade_grupos > total_pontos:
        quantidade_grupos = total_pontos

    # 1. Calcula o limite máximo de lojas por cluster
    teto_por_grupo = int(np.ceil((total_pontos / quantidade_grupos) * fator_teto))

    # 2. Pega pontos iniciais bem distribuídos na lista de lojas para iniciar o KMeans
    posicoes_iniciais = np.linspace(0, total_pontos - 1, quantidade_grupos, dtype=int)
    centroides_iniciais = coordenadas[posicoes_iniciais]

    # 3. Treina o KMeans e pega a tabela de distâncias de cada loja para cada cluster
    modelo_kmeans = KMeans(
        n_clusters=quantidade_grupos,
        init=centroides_iniciais,
        n_init=1,
        max_iter=10,
        random_state=42
    )
    distancias = modelo_kmeans.fit_transform(coordenadas)
    centroides = modelo_kmeans.cluster_centers_

    # 4. Coloca cada loja no cluster mais próximo que ainda tenha vaga disponível
    clusters_finais = [0] * total_pontos
    vagas_ocupadas = [0] * quantidade_grupos

    # Ordena para alocar primeiro as lojas que estão mais próximas do seu centro
    menor_distancia_por_loja = distancias.min(axis=1)
    ordem_lojas = np.argsort(menor_distancia_por_loja)

    for indice_loja in ordem_lojas:
        clusters_mais_proximos = np.argsort(distancias[indice_loja])

        for id_cluster in clusters_mais_proximos:
            if vagas_ocupadas[id_cluster] < teto_por_grupo:
                clusters_finais[indice_loja] = int(id_cluster)
                vagas_ocupadas[id_cluster] += 1
                break

    return clusters_finais, centroides, teto_por_grupo


def rodar_kmeans_e_salvar(df_modelo, dados_normalizados, k_atual, k_sugerido, db):
    print(f"4. Agrupando as lojas por UF com limite de {FATOR_TETO}x (Total GEFINs K={k_atual})...")

    # Separa os GEFINs e GECOMs ativos por UF usando dicionários simples
    colaboradores = list(db["colaboradores"].find({"ativo": True}))
    gefins_por_uf = {}
    gecoms_por_uf = {}

    for colab in colaboradores:
        uf = colab.get("base_operacional", {}).get("uf", "SP")
        tipo = colab.get("tipo_colaborador")

        if tipo == "GEFIN":
            if uf not in gefins_por_uf:
                gefins_por_uf[uf] = []
            gefins_por_uf[uf].append(colab)
        elif tipo == "GECOM":
            if uf not in gecoms_por_uf:
                gecoms_por_uf[uf] = []
            gecoms_por_uf[uf].append(colab)

    operacoes_lojas = []
    operacoes_colab = []
    docs_backup = []
    cluster_offset = 0

    for uf, df_uf in df_modelo.groupby("uf"):
        # Ordena as lojas da UF por latitude e longitude
        df_uf = df_uf.sort_values(["lat_ajustada", "lon_ajustada"]).copy()

        lista_gefins = gefins_por_uf.get(uf, [])
        lista_gecoms = gecoms_por_uf.get(uf, [])

        total_lojas_uf = len(df_uf)
        qtd_gefins_uf = max(1, len(lista_gefins))
        qtd_gecoms_uf = max(1, len(lista_gecoms))

        coordenadas_uf = df_uf[["lat_ajustada", "lon_ajustada"]].values

        # Passo A: Agrupa as Lojas nos GEFINs da UF respeitando o teto de 1.15x
        rotulos_lojas, centroides_gefins, teto_lojas = agrupar_com_limite(
            coordenadas_uf, qtd_gefins_uf, fator_teto=FATOR_TETO
        )
        df_uf["cluster_local"] = rotulos_lojas

        # Passo B: Agrupa os GEFINs nos GECOMs da UF para ficarem na mesma região
        rotulos_gecom, centroides_gecoms, teto_gecoms = agrupar_com_limite(
            centroides_gefins, qtd_gecoms_uf, fator_teto=FATOR_TETO
        )

        # Atualiza o GECOM de cada GEFIN para não ficarem espalhados pelo estado
        for indice_gf in range(len(centroides_gefins)):
            if indice_gf < len(lista_gefins) and len(lista_gecoms) > 0:
                indice_gecom = int(rotulos_gecom[indice_gf])
                gecom_escolhido = lista_gecoms[indice_gecom]

                operacoes_colab.append(
                    UpdateOne(
                        {"_id": lista_gefins[indice_gf]["_id"]},
                        {"$set": {"hierarquia.gecom_responsavel_id": str(gecom_escolhido["_id"])}}
                    )
                )

        # Prepara a atualização de cada loja no Cosmos DB e no backup do Data Lake
        for indice, row in df_uf.iterrows():
            cluster_local = int(row["cluster_local"])
            cluster_global = int(cluster_offset + cluster_local)

            if cluster_local < len(lista_gefins):
                novo_gefin = str(lista_gefins[cluster_local]["_id"])
            else:
                novo_gefin = row["gefin_atual"]

            operacoes_lojas.append(
                UpdateOne(
                    {"cnpj": row["cnpj_loja"]},
                    {"$set": {"cluster_id": cluster_global, "gefin_id": novo_gefin}}
                )
            )

            docs_backup.append({
                "cnpj_loja": row["cnpj_loja"],
                "cluster_id": cluster_global,
                "gefin_id": novo_gefin,
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "producao_media": row["producao_media"]
            })

        cluster_offset += qtd_gefins_uf
        print(f" -> UF {uf}: {total_lojas_uf} lojas em {qtd_gefins_uf} clusters (teto: {teto_lojas} lojas/GEFIN).")

    print("5. Salvando o cluster_id no Cosmos DB e no Data Lake...")
    lote_size = 1000
    for i in range(0, len(operacoes_colab), lote_size):
        db["colaboradores"].bulk_write(operacoes_colab[i:i + lote_size])
    for i in range(0, len(operacoes_lojas), lote_size):
        db["lojas"].bulk_write(operacoes_lojas[i:i + lote_size])

    print(" -> Cosmos DB atualizado com sucesso!")

    # Faz o upload do backup para a camada Gold
    datalake.upload_json("gold", "modelagem_final/lojas_clusterizadas_gold.json", docs_backup)
    print(" -> Backup salvo no Data Lake (gold/modelagem_final/lojas_clusterizadas_gold.json).")

def main():
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
        cosmos_db.fechar()

if __name__ == "__main__":
    main()