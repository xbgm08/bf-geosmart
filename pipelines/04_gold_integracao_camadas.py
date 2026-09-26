import os
import random
from collections import defaultdict
from dotenv import load_dotenv
from pymongo import MongoClient
from services.datalake_service import datalake

def distribuir_lojas_gefin(lojas, gefins, rng):
    """Atribui lojas reais aos GEFINs com pesos (Ouro/Prata/Bronze) e coordenadas aproximadas."""
    dict_gefins = {g['_id']: g for g in gefins}
    ids_gefins = list(dict_gefins.keys())
    
    lojas_por_gefin = defaultdict(list)
    
    for loja in lojas:
        gefin_id = rng.choice(ids_gefins)
        gefin = dict_gefins[gefin_id]
        
        sorteio = rng.random()
        if sorteio > 0.85:
            peso, tier = 5.0, "OURO"   # 15% das lojas puxam muito volume
        elif sorteio > 0.50:
            peso, tier = 2.0, "PRATA"  # 35% das lojas têm volume médio
        else:
            peso, tier = 1.0, "BRONZE" # 50% das lojas têm volume baixo
            
        # Coordenada do GEFIN + variação aleatória de 5 a 30 km
        lon_base, lat_base = gefin['base_operacional']['coordinates']
        lon_loja = round(lon_base + rng.uniform(-0.06, 0.06), 6)
        lat_loja = round(lat_base + rng.uniform(-0.06, 0.06), 6)
        
        loja['gefin_id'] = gefin_id
        loja['tier_loja'] = tier
        loja['peso_distribuicao'] = peso
        loja['localizacao'] = {
            "type": "Point",
            "coordinates": [lon_loja, lat_loja]
        }
        loja['historico_share'] = [] 
        lojas_por_gefin[gefin_id].append(loja)
        
    return lojas, lojas_por_gefin

def processar_rateio_share(historico_gefins, lojas_por_gefin, rng):
    """Rateio Reverso: Distribui a performance do GEFIN para as suas respetivas lojas."""
    hist_por_gefin = defaultdict(list)
    for h in historico_gefins:
        hist_por_gefin[h['gefin_id']].append(h)
        
    for gefin_id, lojas_carteira in lojas_por_gefin.items():
        if not lojas_carteira: continue
            
        historicos_mensais = hist_por_gefin.get(gefin_id, [])
        for hist in historicos_mensais:
            for loja in lojas_carteira:
                variacao = rng.uniform(-0.01, 0.05) if loja['tier_loja'] == "OURO" else rng.uniform(-0.04, 0.01)
                share_loja = round(max(0.001, min(1.0, hist['share'] + variacao)), 4)
                
                loja['historico_share'].append({
                    "mes_referencia": hist['mes_referencia'],
                    "share_estimado": share_loja
                })

def amarrar_propostas_lojas(propostas, lojas_por_gefin, rng):
    """Vincula o CNPJ da loja à proposta usando um sorteio viciado pelo Peso da loja."""
    for prop in propostas:
        lojas_carteira = lojas_por_gefin.get(prop['gefin_id'], [])
        
        if lojas_carteira:
            # Sorteio onde a Loja Ouro tem 5x mais hipóteses de gerar uma proposta
            pesos = [loja['peso_distribuicao'] for loja in lojas_carteira]
            loja_sorteada = rng.choices(lojas_carteira, weights=pesos, k=1)[0]
            
            # Enriquecimento da proposta com o mundo real
            prop['cnpj_loja'] = loja_sorteada['cnpj']
            prop['razao_social'] = loja_sorteada['razao_social']

def main():
    load_dotenv(override=True)
    rng = random.Random(2026)
    
    print("1. A extrair dados do Data Lake (Camada Silver)...")
    lojas_silver = datalake.download_json("silver", "api_receita/lojas_silver.json")
    colaboradores = datalake.download_json("silver", "dados_sinteticos/colaboradores.json")
    propostas = datalake.download_json("silver", "dados_sinteticos/propostas.json")
    historico_share = datalake.download_json("silver", "dados_sinteticos/historico_share.json")

    print("\n2. A iniciar a Transformação para a Camada GOLD...")
    gefins = [c for c in colaboradores if c['cargo'] == 'GEFIN']
    
    print(" -> A carteirizar lojas reais e a gerar Mock GeoJSON...")
    lojas_gold, lojas_por_gefin = distribuir_lojas_gefin(lojas_silver, gefins, rng)
    
    print(" -> A realizar o rateio matemático do histórico financeiro...")
    processar_rateio_share(historico_share, lojas_por_gefin, rng)
    
    print(" -> A amarrar as propostas aos CNPJs sorteados...")
    amarrar_propostas_lojas(propostas, lojas_por_gefin, rng)
    
    # Limpeza final das variáveis de cálculo temporárias nas Lojas
    for loja in lojas_gold:
        loja.pop('peso_distribuicao', None)

    print("\n3. A guardar as bases enriquecidas finais na camada GOLD...")
    datalake.upload_json("gold", "modelagem_final/lojas_gold.json", lojas_gold)
    datalake.upload_json("gold", "modelagem_final/propostas_gold.json", propostas)
    datalake.upload_json("gold", "modelagem_final/colaboradores_gold.json", colaboradores)
    
    print("\n4. A inserir dados na API MongoDB do Azure Cosmos DB (O 'C' do CRUD)...")
    uri_mongo = os.getenv("COSMOS_MONGO_URI")
    db_name = os.getenv("COSMOS_DB_NAME", "bf_geosmart")
    
    client = MongoClient(uri_mongo)
    db = client[db_name]
    
    # Limpeza das coleções antigas
    for col in ['lojas', 'propostas', 'colaboradores']:
        db[col].drop()
    
    db['lojas'].insert_many(lojas_gold)
    print(f" -> Lojas carregadas com sucesso: {db['lojas'].count_documents({})}")
    
    db['colaboradores'].insert_many(colaboradores)
    print(f" -> Colaboradores carregados com sucesso: {db['colaboradores'].count_documents({})}")
    
    db['propostas'].insert_many(propostas)
    print(f" -> Propostas carregadas com sucesso: {db['propostas'].count_documents({})}")
    
    print("\nIntegração Gold concluída!")

if __name__ == "__main__":
    main()