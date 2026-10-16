import os
import time
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from tqdm import tqdm

load_dotenv(override=True)
uri_mongo = os.getenv("COSMOS_MONGO_URI")
db_name = os.getenv("COSMOS_DB_NAME", "bf_geosmart")

client = MongoClient(uri_mongo)
db = client[db_name]
lojas_col = db['lojas']

# Identificador da nossa aplicação para o serviço de mapas
geolocator = Nominatim(user_agent="bf_geosmart_tcc_fatec")

def buscar_coordenadas(endereco, retries=3):
    """Função para buscar a latitude e longitude do endereço da loja na API do Nominatim."""
    try:
        location = geolocator.geocode(endereco, timeout=5)
        if location:
            return [location.longitude, location.latitude]
        return None
    except (GeocoderTimedOut, GeocoderServiceError):
        # Se a API falhar ou demorar, espera 2 segundos e tenta de novo
        if retries > 0:
            time.sleep(2)
            return buscar_coordenadas(endereco, retries - 1)
        return None

def rodar_geocodificacao_batch():
    # Filtra apenas as lojas que ainda não passaram por esse processo
    query_pendentes = {"geocodificado_real": {"$exists": False}}
    total_pendentes = lojas_col.count_documents(query_pendentes)
    
    if total_pendentes == 0:
        print("Todas as lojas já estão com as coordenadas reais!")
        return

    print(f"Iniciando busca de coordenadas para {total_pendentes} lojas...")
    
    # Traz para a memória apenas os campos necessários para montar o endereço
    projecao = {
        "_id": 1, 
        "endereco_logradouro": 1, 
        "endereco_numero": 1, 
        "endereco_bairro": 1, 
        "endereco_municipio": 1, 
        "endereco_uf": 1
    }
    lojas_pendentes = list(lojas_col.find(query_pendentes, projecao))
    
    operacoes = []
    lote_tamanho = 100 # Agrupa as atualizações para não sobrecarregar o banco de dados
    
    for loja in tqdm(lojas_pendentes, total=total_pendentes, desc="Processando Lote"):
        logradouro = loja.get('endereco_logradouro', '')
        numero = loja.get('endereco_numero', '')
        bairro = loja.get('endereco_bairro', '')
        municipio = loja.get('endereco_municipio', '')
        uf = loja.get('endereco_uf', '')
        
        # Concatena os campos para formar o endereço completo
        endereco = f"{logradouro}, {numero}, {bairro}, {municipio}, {uf}, Brasil"
        endereco = endereco.replace(" ,", "").replace(", ,", ",")
        
        coordenadas = buscar_coordenadas(endereco)
        
        if coordenadas:
            # Estrutura padrão GeoJSON exigida pelo MongoDB para mapas
            localizacao_geojson = {
                "type": "Point",
                "coordinates": coordenadas
            }
            
            # Prepara o comando para atualizar a loja no banco
            operacao = UpdateOne(
                {"_id": loja["_id"]},
                {"$set": {
                    "localizacao": localizacao_geojson,
                    "geocodificado_real": True # Marca que a loja já foi atualizada
                }}
            )
            operacoes.append(operacao)
        else:
            # Caso o endereço não seja encontrado no mapa
            operacao = UpdateOne(
                {"_id": loja["_id"]},
                {"$set": {"geocodificado_real": "nao_encontrado"}}
            )
            operacoes.append(operacao)
        
        # Pausa obrigatória para não ser bloqueado pela API gratuita do OpenStreetMap
        time.sleep(1.1)
        
        # Executa a atualização no Cosmos DB a cada 100 lojas
        if len(operacoes) >= lote_tamanho:
            lojas_col.bulk_write(operacoes, ordered=False)
            operacoes.clear()
            
    # Atualiza as últimas lojas que sobraram na lista
    if operacoes:
        lojas_col.bulk_write(operacoes, ordered=False)
        
    print("\nAtualização de coordenadas finalizada com sucesso!")

if __name__ == "__main__":
    rodar_geocodificacao_batch()