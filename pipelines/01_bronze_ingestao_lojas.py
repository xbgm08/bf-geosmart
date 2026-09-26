import requests
from services.datalake_service import datalake

CNAES_ALVO = {
    "4511102": 15000, # Carros usados
    "4512902": 10000, # Consignação / Multimarcas
    "4541204": 5000,  # Motos usadas
    "4511101": 3000,  # Carros novos
    "4541203": 1500,  # Motos novas
    "4511104": 1000,  # Caminhões
    "4511106": 500    # Ônibus e micro-ônibus
}

def buscar_empresas_por_cnae(cnae: str, limite_desejado: int):
    """Realiza requisições paginadas na Minha Receita até atingir o limite."""
    empresas_coletadas = []
    cursor = None
    url = "https://minhareceita.org/"
    headers = {"User-Agent": "BF-GeoSmart-DataLake/1.0"}
    
    while len(empresas_coletadas) < limite_desejado:
        params = {
            "cnae": cnae,
            "limit": 1000
        }
        if cursor:
            params["cursor"] = cursor
            
        print(f"   -> Baixando página... (Progresso: {len(empresas_coletadas)}/{limite_desejado})")
        
        response = requests.get(url, params=params, headers=headers, timeout=60)
        
        if response.status_code == 200:
            dados = response.json()
            lote = dados.get("data", [])
            
            # A API não tem mais dados para este CNAE
            if not lote:
                break 
                
            empresas_coletadas.extend(lote)
            
            # Atualiza o cursor para a próxima página
            cursor = dados.get("cursor")

            # Verifica se acabou as páginas
            if not cursor:
                break
        else:
            print(f"   -> Erro na API: Status {response.status_code}")
            break

    return empresas_coletadas[:limite_desejado]

def main():
    print("Iniciando extração massiva e paginada de lojas via Minha Receita...\n")
    lojas_coletadas = []

    for cnae, limite in CNAES_ALVO.items():
        print(f"Buscando dados para o CNAE {cnae} (Meta: {limite} lojas)...")
        
        empresas = buscar_empresas_por_cnae(cnae, limite)
        
        if empresas:
            lojas_coletadas.extend(empresas)
            print(f"-> {len(empresas)} lojas validadas e adicionadas.\n")
        else:
            print("-> Nenhuma empresa encontrada.\n")

    if lojas_coletadas:
        total = len(lojas_coletadas)
        print(f"Extração concluída! {total} lojas coletadas no total.")
        
        # Salva o resultado no Data Lake
        caminho_blob = "api_receita/lojas_raw.json"
        datalake.upload_json("bronze", caminho_blob, lojas_coletadas)
    else:
        print("Nenhum dado foi coletado.")

if __name__ == "__main__":
    main()