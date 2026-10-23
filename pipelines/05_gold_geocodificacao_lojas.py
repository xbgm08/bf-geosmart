import os
import re
import time
import random
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError, OperationFailure
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from tqdm import tqdm
from services.datalake_service import datalake

load_dotenv(override=True)
uri_mongo = os.getenv("COSMOS_MONGO_URI")
db_name = os.getenv("COSMOS_DB_NAME", "bf_geosmart")

client = MongoClient(uri_mongo, serverSelectionTimeoutMS=20000)
db = client[db_name]
lojas_col = db["lojas"]

# Identificador da nossa aplicação para o serviço de mapas
geolocator = Nominatim(user_agent="bf_geosmart_tcc_fatec")

# Cache em memória para não repetir chamadas HTTP de ruas, bairros ou municípios já consultados
cache_coordenadas = {}

# Coordenadas centrais das UFs como último fallback de segurança
CENTROIDES_UF = {
    "AC": [-70.55, -9.02],
    "AL": [-36.66, -9.57],
    "AM": [-64.63, -3.41],
    "AP": [-51.77, 1.41],
    "BA": [-41.70, -12.57],
    "CE": [-39.32, -5.49],
    "DF": [-47.88, -15.79],
    "ES": [-40.30, -19.18],
    "GO": [-49.25, -16.68],
    "MA": [-45.27, -4.96],
    "MG": [-44.38, -18.51],
    "MS": [-54.54, -20.44],
    "MT": [-55.42, -12.68],
    "PA": [-52.48, -3.79],
    "PB": [-36.72, -7.23],
    "PE": [-37.86, -8.28],
    "PI": [-42.72, -7.71],
    "PR": [-51.55, -24.89],
    "RJ": [-43.17, -22.90],
    "RN": [-36.52, -5.79],
    "RO": [-62.80, -10.83],
    "RR": [-61.33, 2.05],
    "RS": [-53.25, -30.03],
    "SC": [-50.21, -27.24],
    "SE": [-37.38, -10.57],
    "SP": [-46.63, -23.55],
    "TO": [-48.29, -10.17],
}

def limpar_numero(numero: str) -> str:
    """Ignora números inválidos da Receita Federal como S/N, SN ou KM."""
    if not numero:
        return ""
    num_limpo = str(numero).strip().upper()
    if num_limpo in ("S/N", "SN", "S/Nº", "0", "SEM NUMERO", "KM"):
        return ""
    # Mantém apenas se tiver dígitos e não for marcação de quilometragem
    if "KM" in num_limpo:
        return ""
    return num_limpo

def limpar_logradouro(logradouro: str) -> str:
    """Remove excesso de espaços e caracteres que atrapalham a busca no Nominatim."""
    if not logradouro:
        return ""
    texto = re.sub(r"\s+", " ", str(logradouro)).strip()
    return texto

def consultar_nominatim_com_cache(consulta: str, retries=3):
    """Consulta o Nominatim respeitando o cache em memória e o rate limit de 1.1s."""
    chave = consulta.strip().upper()
    if chave in cache_coordenadas:
        return cache_coordenadas[chave]

    try:
        # Pausa apenas quando realmente vai fazer requisição externa
        time.sleep(1.1)
        location = geolocator.geocode(consulta, timeout=10, country_codes="br")
        if location:
            coords = [round(location.longitude, 6), round(location.latitude, 6)]
            cache_coordenadas[chave] = coords
            return coords
        cache_coordenadas[chave] = None
        return None
    except (GeocoderTimedOut, GeocoderServiceError):
        if retries > 0:
            time.sleep(2)
            return consultar_nominatim_com_cache(consulta, retries - 1)
        return None


def aplicar_jitter(coords: list, raio_graus: float, semente: str) -> list:
    """Aplica um pequeno deslocamento determinístico para evitar pontos sobrepostos no K-Means."""
    rng = random.Random(semente)
    lon = round(coords[0] + rng.uniform(-raio_graus, raio_graus), 6)
    lat = round(coords[1] + rng.uniform(-raio_graus, raio_graus), 6)
    return [lon, lat]

def geocodificar_em_cascata(loja: dict):
    """
    Tenta localizar a loja em 4 níveis de precisão:
    1. Logradouro + Número + Município + UF
    2. Logradouro + Município + UF (com micro-jitter de ~80m)
    3. Bairro + Município + UF (com jitter de ~350m)
    4. Município + UF (em cache, com jitter urbano de ~1.2km)
    """
    cnpj = str(loja.get("cnpj") or loja.get("_id"))
    logradouro = limpar_logradouro(loja.get("endereco_logradouro", ""))
    numero = limpar_numero(loja.get("endereco_numero", ""))
    bairro = str(loja.get("endereco_bairro", "")).strip()
    municipio = str(loja.get("endereco_municipio", "")).strip()
    uf = str(loja.get("endereco_uf", "")).strip().upper()

    # Nível 1: Rua + Número + Cidade + UF (Sem bairro para evitar falso negativo do OSM)
    if logradouro and numero and municipio and uf:
        q1 = f"{logradouro}, {numero}, {municipio}, {uf}, Brasil"
        coords = consultar_nominatim_com_cache(q1)
        if coords:
            return aplicar_jitter(coords, 0.00015, cnpj), "logradouro_numero"

    # Nível 2: Apenas Rua + Cidade + UF
    if logradouro and municipio and uf:
        q2 = f"{logradouro}, {municipio}, {uf}, Brasil"
        coords = consultar_nominatim_com_cache(q2)
        if coords:
            return aplicar_jitter(coords, 0.0008, cnpj), "logradouro"

    # Nível 3: Bairro + Cidade + UF
    if bairro and municipio and uf:
        q3 = f"{bairro}, {municipio}, {uf}, Brasil"
        coords = consultar_nominatim_com_cache(q3)
        if coords:
            return aplicar_jitter(coords, 0.0035, cnpj), "bairro"

    # Nível 4: Centroide do Município + UF (Altíssima taxa de acerto via Cache)
    if municipio and uf:
        q4 = f"{municipio}, {uf}, Brasil"
        coords = consultar_nominatim_com_cache(q4)
        if coords:
            return aplicar_jitter(coords, 0.012, cnpj), "municipio"

    # Fallback final por UF (Garante que nenhuma loja fique sem coordenada)
    base_uf = CENTROIDES_UF.get(uf, [-46.6333, -23.5505])
    return aplicar_jitter(base_uf, 0.05, cnpj), "uf_fallback"

def executar_bulk_seguro(colecao, operacoes):
    """Executa bulk_write tratando erro 16500 (Rate Limit RU/s do Azure Cosmos DB)."""
    pendentes = list(operacoes)
    while pendentes:
        try:
            colecao.bulk_write(pendentes, ordered=False)
            break
        except BulkWriteError as bwe:
            erros = bwe.details.get("writeErrors", [])
            indices_16500 = [e["index"] for e in erros if e.get("code") == 16500]
            if indices_16500:
                pendentes = [pendentes[idx] for idx in indices_16500]
                time.sleep(1.5)
            else:
                break
        except OperationFailure as erro:
            if erro.code == 16500 or "16500" in str(erro):
                time.sleep(1.5)
            else:
                raise

def rodar_geocodificacao_batch():
    # Busca todas as lojas que ainda não têm geocodificado_real == True
    # (inclui as que ficaram como "nao_encontrado", False ou sem o campo)
    query_pendentes = {
        "$or": [
            {"geocodificado_real": {"$ne": True}},
            {"localizacao.coordinates": {"$exists": False}},
        ]
    }
    total_pendentes = lojas_col.count_documents(query_pendentes)

    if total_pendentes == 0:
        print("Todas as lojas do Cosmos DB já estão geocodificadas com sucesso!")
        return

    print(
        f"Iniciando geocodificação inteligente para {total_pendentes} lojas pendentes..."
    )

    projecao = {
        "_id": 1,
        "cnpj": 1,
        "endereco_logradouro": 1,
        "endereco_numero": 1,
        "endereco_bairro": 1,
        "endereco_municipio": 1,
        "endereco_uf": 1,
    }
    lojas_pendentes = list(lojas_col.find(query_pendentes, projecao))

    operacoes = []
    lote_tamanho = 150
    contagem_niveis = {}

    for loja in tqdm(
        lojas_pendentes, total=total_pendentes, desc="Geocodificando Lojas"
    ):
        coordenadas, nivel = geocodificar_em_cascata(loja)
        contagem_niveis[nivel] = contagem_niveis.get(nivel, 0) + 1

        operacao = UpdateOne(
            {"_id": loja["_id"]},
            {
                "$set": {
                    "localizacao": {"type": "Point", "coordinates": coordenadas},
                    "geocodificado_real": True,
                    "precisao_geocodificacao": nivel,
                }
            },
        )
        operacoes.append(operacao)

        if len(operacoes) >= lote_tamanho:
            executar_bulk_seguro(lojas_col, operacoes)
            operacoes.clear()

    if operacoes:
        executar_bulk_seguro(lojas_col, operacoes)
        operacoes.clear()

    print("\nResumo de precisão da geocodificação:")
    for nivel, qtd in contagem_niveis.items():
        print(f" -> {nivel}: {qtd} lojas")

    # Atualiza o snapshot de lojas na camada Gold do Data Lake para manter consistência
    print("\nSincronizando base de lojas atualizada com a camada Gold do Data Lake...")
    lojas_gold = list(lojas_col.find({}, {"_id": 0}))
    datalake.upload_json("gold", "modelagem_final/lojas_gold.json", lojas_gold)
    print(
        f" -> gold/modelagem_final/lojas_gold.json atualizado ({len(lojas_gold)} lojas)!"
    )

if __name__ == "__main__":
    try:
        rodar_geocodificacao_batch()
    finally:
        client.close()
