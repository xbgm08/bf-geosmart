import os
import math
import time
import requests
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from services.datalake_service import datalake

RAIO_TERRA_KM = 6371.0

# Pesos da recomendação (Total = 1.00 -> 100 pontos)
PESO_REGIONAL = 0.30
PESO_TEMPO = 0.40
PESO_CARGA = 0.30

# Parâmetros usados apenas no Fallback (Haversine)
FATOR_CURVAS_RUA = 1.3
VELOCIDADE_MEDIA_KMH = 50.0
TEMPO_MAXIMO_MIN = 240.0

# Configuração da API de Matriz Viária do OSRM (OpenStreetMap)
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving"
TAMANHO_LOTE_LOJAS = 50
MAX_GEFINS_POR_CONSULTA = 25


def conectar_banco():
    uri = os.getenv("COSMOS_MONGO_URI") or os.getenv("COSMOS_MONGO_CONNECTION_STRING")
    if not uri:
        raise ValueError("Defina COSMOS_MONGO_URI no arquivo .env.")
    banco = os.getenv("COSMOS_DB_NAME", "bf_geosmart")
    cliente = MongoClient(uri, serverSelectionTimeoutMS=20000)
    return cliente, cliente[banco]


def calcular_distancia_haversine_km(lat1, lon1, lat2, lon2):
    """Calcula a distância em linha reta (Haversine) em km."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * (math.sin(delta_lon / 2) ** 2)
    )
    if a > 1.0:
        a = 1.0
    return 2 * RAIO_TERRA_KM * math.asin(math.sqrt(a))


def calcular_haversine_fallback(lat_origem, lon_origem, lat_destino, lon_destino):
    """Fallback: estima distância e tempo apenas quando a API do OSRM falhar."""
    distancia_reta = calcular_distancia_haversine_km(lat_origem, lon_origem, lat_destino, lon_destino)
    distancia_viaria_km = distancia_reta * FATOR_CURVAS_RUA
    tempo_minutos = (distancia_viaria_km / VELOCIDADE_MEDIA_KMH) * 60.0
    return round(tempo_minutos, 1), round(distancia_viaria_km, 1)


def consultar_matriz_osrm(lote_lojas, gestores_candidatos):
    """
    Modelo Principal: Consulta o endpoint /table do OSRM (OpenStreetMap) para obter
    a matriz de tempos reais (segundos) e distâncias reais de rua (metros) de um lote
    de lojas para todos os GEFINs candidatos em 1 única requisição HTTP.
    """
    coordenadas_str = []

    # 1. Adiciona as coordenadas das lojas (origens)
    for loja in lote_lojas:
        coordenadas_str.append(f"{loja['lon']},{loja['lat']}")

    # 2. Adiciona as coordenadas dos GEFINs (destinos)
    for gestor in gestores_candidatos:
        coordenadas_str.append(f"{gestor['lon']},{gestor['lat']}")

    qtd_lojas = len(lote_lojas)
    qtd_gestores = len(gestores_candidatos)

    indices_origens = [str(i) for i in range(qtd_lojas)]
    indices_destinos = [str(qtd_lojas + j) for j in range(qtd_gestores)]

    bloco_coords = ";".join(coordenadas_str)
    param_sources = ";".join(indices_origens)
    param_destinations = ";".join(indices_destinos)

    url = (
        f"{OSRM_TABLE_URL}/{bloco_coords}"
        f"?sources={param_sources}&destinations={param_destinations}"
        f"&annotations=duration,distance"
    )

    try:
        resposta = requests.get(url, timeout=12)
        if resposta.status_code == 200:
            dados = resposta.json()
            if dados.get("code") == "Ok":
                matriz_tempos = dados.get("durations")
                matriz_distancias = dados.get("distances")
                return matriz_tempos, matriz_distancias, True
    except Exception:
        pass

    return None, None, False


def selecionar_gefins_proximos_do_lote(lote_lojas, lista_gestores):
    """
    Se a UF tiver mais de 25 GEFINs (como SP), seleciona os 25 GEFINs mais próximos
    da região do lote para respeitar o limite de coordenadas da API pública do OSRM.
    """
    elegiveis = []
    for gestor in lista_gestores:
        if gestor["carga_atual"] < gestor["capacidade_max"]:
            elegiveis.append(gestor)

    if len(elegiveis) <= MAX_GEFINS_POR_CONSULTA:
        return elegiveis

    # Calcula o centro do lote de lojas
    soma_lat = 0.0
    soma_lon = 0.0
    for loja in lote_lojas:
        soma_lat += loja["lat"]
        soma_lon += loja["lon"]

    lat_media = soma_lat / len(lote_lojas)
    lon_media = soma_lon / len(lote_lojas)

    # Ordena os GEFINs pela proximidade ao lote de lojas
    elegiveis_ordenados = sorted(
        elegiveis,
        key=lambda g: calcular_distancia_haversine_km(lat_media, lon_media, g["lat"], g["lon"])
    )
    return elegiveis_ordenados[:MAX_GEFINS_POR_CONSULTA]


def carregar_lojas_e_gestores(db):
    print("1. Lendo Lojas e GEFINs diretamente do Cosmos DB...")

    cursor_lojas = db["lojas"].find(
        {"localizacao": {"$exists": True}},
        {
            "_id": 1,
            "cnpj": 1,
            "razao_social": 1,
            "nome_fantasia": 1,
            "endereco_uf": 1,
            "gefin_id": 1,
            "localizacao": 1,
        },
    )

    lojas_por_uf = {}
    contagem_por_gefin = {}
    soma_coords_gefin = {}
    total_lojas = 0

    for doc in cursor_lojas:
        coords = doc.get("localizacao", {}).get("coordinates", [])
        if len(coords) != 2:
            continue

        lon, lat = float(coords[0]), float(coords[1])
        gefin_id = str(doc.get("gefin_id", ""))
        uf = str(doc.get("endereco_uf", "SP")).strip().upper()

        loja_info = {
            "_id": doc["_id"],
            "cnpj": str(doc.get("cnpj")),
            "nome": doc.get("nome_fantasia") or doc.get("razao_social") or "Loja",
            "uf": uf,
            "gefin_atual": gefin_id,
            "lat": lat,
            "lon": lon,
        }

        if uf not in lojas_por_uf:
            lojas_por_uf[uf] = []
        lojas_por_uf[uf].append(loja_info)
        total_lojas += 1

        if gefin_id:
            contagem_por_gefin[gefin_id] = contagem_por_gefin.get(gefin_id, 0) + 1
            if gefin_id not in soma_coords_gefin:
                soma_coords_gefin[gefin_id] = [0.0, 0.0, 0]
            soma_coords_gefin[gefin_id][0] += lat
            soma_coords_gefin[gefin_id][1] += lon
            soma_coords_gefin[gefin_id][2] += 1

    maior_carteira = max(contagem_por_gefin.values()) if contagem_por_gefin else 40
    capacidade_padrao = max(10, int(math.ceil(maior_carteira * 1.25)))

    cursor_gefins = db["colaboradores"].find({"tipo_colaborador": "GEFIN", "ativo": True})
    gestores_por_uf = {}
    todos_gestores = []

    for doc in cursor_gefins:
        gid = str(doc["_id"])
        base = doc.get("base_operacional") or {}
        uf = str(base.get("uf", "SP")).strip().upper()
        carga_atual = contagem_por_gefin.get(gid, 0)
        capacidade_max = max(capacidade_padrao, carga_atual + 1)

        if gid in soma_coords_gefin and soma_coords_gefin[gid][2] > 0:
            soma = soma_coords_gefin[gid]
            lat_gestor = soma[0] / soma[2]
            lon_gestor = soma[1] / soma[2]
        else:
            coords_base = base.get("coordinates", [])
            if len(coords_base) != 2:
                continue
            lon_gestor, lat_gestor = float(coords_base[0]), float(coords_base[1])

        gestor_info = {
            "id": gid,
            "nome": doc.get("nome", gid),
            "uf": uf,
            "lat": lat_gestor,
            "lon": lon_gestor,
            "carga_atual": carga_atual,
            "capacidade_max": capacidade_max,
        }

        todos_gestores.append(gestor_info)
        if uf not in gestores_por_uf:
            gestores_por_uf[uf] = []
        gestores_por_uf[uf].append(gestor_info)

    print(f" -> {total_lojas} lojas e {len(todos_gestores)} GEFINs ativos carregados (Capacidade teto: {capacidade_padrao}).")
    return lojas_por_uf, gestores_por_uf, todos_gestores


def executar():
    load_dotenv(override=True)
    cliente, db = conectar_banco()

    try:
        lojas_por_uf, gestores_por_uf, todos_gestores = carregar_lojas_e_gestores(db)
        if not lojas_por_uf or not todos_gestores:
            print("Aviso: Lojas ou GEFINs insuficientes para gerar recomendações.")
            return

        print("2. Calculando Top 3 GEFINs via malha viária real OSRM (/table) com Haversine de fallback...")
        operacoes_banco = []
        backup_gold = []
        total_rotas_osrm = 0
        total_rotas_fallback = 0
        amostras_impressas = 0

        for uf in sorted(lojas_por_uf.keys()):
            # Ordena as lojas por latitude e longitude para que cada lote de 50 seja da mesma vizinhança
            lojas_uf = sorted(lojas_por_uf[uf], key=lambda item: (item["lat"], item["lon"]))
            gestores_uf = gestores_por_uf.get(uf, [])
            if len(gestores_uf) < 3:
                gestores_uf = todos_gestores

            for inicio in range(0, len(lojas_uf), TAMANHO_LOTE_LOJAS):
                lote_lojas = lojas_uf[inicio : inicio + TAMANHO_LOTE_LOJAS]
                candidatos = selecionar_gefins_proximos_do_lote(lote_lojas, gestores_uf)

                # Consulta a matriz viária real no OSRM para o lote inteiro de uma vez
                matriz_tempos, matriz_distancias, sucesso_osrm = consultar_matriz_osrm(
                    lote_lojas, candidatos
                )

                for indice_loja in range(len(lote_lojas)):
                    loja = lote_lojas[indice_loja]
                    avaliacoes = []

                    for indice_gestor in range(len(candidatos)):
                        gestor = candidatos[indice_gestor]

                        # Verifica se o OSRM retornou tempo e distância válidos para este par
                        tempo_osrm = None
                        dist_osrm = None
                        if sucesso_osrm and matriz_tempos and matriz_distancias:
                            tempo_osrm = matriz_tempos[indice_loja][indice_gestor]
                            dist_osrm = matriz_distancias[indice_loja][indice_gestor]

                        if tempo_osrm is not None and dist_osrm is not None:
                            tempo_min = round(float(tempo_osrm) / 60.0, 1)
                            distancia_km = round(float(dist_osrm) / 1000.0, 1)
                            fonte_tempo = "rota viária (OSRM)"
                            total_rotas_osrm += 1
                        else:
                            # Fallback: só usa Haversine se o OSRM falhar
                            tempo_min, distancia_km = calcular_haversine_fallback(
                                loja["lat"], loja["lon"], gestor["lat"], gestor["lon"]
                            )
                            fonte_tempo = "estimado (Haversine)"
                            total_rotas_fallback += 1

                        nota_regional = 1.0 if gestor["uf"] == loja["uf"] else 0.0
                        nota_tempo = max(0.0, 1.0 - (tempo_min / TEMPO_MAXIMO_MIN))
                        nota_carga = max(0.0, 1.0 - (gestor["carga_atual"] / gestor["capacidade_max"]))

                        score_final = 100.0 * (
                            (PESO_REGIONAL * nota_regional)
                            + (PESO_TEMPO * nota_tempo)
                            + (PESO_CARGA * nota_carga)
                        )

                        avaliacoes.append({
                            "gestor_id": gestor["id"],
                            "gestor_nome": gestor["nome"],
                            "regional_gestor": gestor["uf"],
                            "score": round(score_final, 2),
                            "distancia_km": distancia_km,
                            "tempo_viario_min": tempo_min,
                            "fonte_tempo": fonte_tempo,
                            "carga_atual": gestor["carga_atual"],
                            "capacidade_max": gestor["capacidade_max"],
                        })

                    avaliacoes.sort(key=lambda item: item["score"], reverse=True)
                    top3 = avaliacoes[:3]

                    for indice_rec in range(len(top3)):
                        rec = top3[indice_rec]
                        posicao = indice_rec + 1
                        rec["posicao"] = posicao
                        vagas_livres = rec["capacidade_max"] - rec["carga_atual"]

                        rec["justificativa"] = (
                            f"{rec['gestor_nome']} ficou em {posicao}º lugar com score {rec['score']}/100. "
                            f"Atua na UF {rec['regional_gestor']}; está a {rec['distancia_km']} km / "
                            f"{rec['tempo_viario_min']} min ({rec['fonte_tempo']}) e possui carga de "
                            f"{rec['carga_atual']}/{rec['capacidade_max']} lojas ({vagas_livres} vagas livres)."
                        )

                    if amostras_impressas < 5 and len(top3) > 0:
                        melhor = top3[0]
                        print(
                            f" [Amostra] CNPJ: {loja['cnpj']} ({loja['uf']}) | "
                            f"1º: {melhor['gestor_nome']} | Score: {melhor['score']} | "
                            f"Dist: {melhor['distancia_km']} km ({melhor['tempo_viario_min']} min - {melhor['fonte_tempo']})"
                        )
                        amostras_impressas += 1

                    operacoes_banco.append(
                        UpdateOne(
                            {"_id": loja["_id"]},
                            {"$set": {"recomendacoes_gefin": top3}}
                        )
                    )

                    backup_gold.append({
                        "cnpj_loja": loja["cnpj"],
                        "loja_nome": loja["nome"],
                        "uf": loja["uf"],
                        "gefin_atual": loja["gefin_atual"],
                        "top3_recomendados": top3,
                    })

                # Pequena pausa de 0.1s entre os lotes para respeitar o servidor público do OSRM
                time.sleep(0.1)

            print(f" -> UF {uf} concluída ({len(lojas_uf)} lojas processadas via OSRM).")

        print(f"\n3. Gravando recomendações de {len(operacoes_banco)} lojas no Cosmos DB...")
        tamanho_lote = 1000
        for i in range(0, len(operacoes_banco), tamanho_lote):
            lote = operacoes_banco[i : i + tamanho_lote]
            db["lojas"].bulk_write(lote, ordered=False)
            print(f" -> Progresso Cosmos DB: {min(i + tamanho_lote, len(operacoes_banco))}/{len(operacoes_banco)} lojas salvas...")
            time.sleep(0.3)

        print("4. Salvando backup na camada Gold do Data Lake...")
        datalake.upload_json("gold", "modelagem_final/top3_gefin_gold.json", backup_gold)

        print("\n=== Resumo da Recomendação Viária (Pipeline 09) ===")
        print(f"Total de lojas processadas: {len(operacoes_banco)}")
        print(f"Rotas calculadas pelo Modelo Principal (OSRM Real): {total_rotas_osrm}")
        print(f"Rotas calculadas pelo Fallback (Haversine): {total_rotas_fallback}")

    finally:
        cliente.close()


if __name__ == "__main__":
    executar()