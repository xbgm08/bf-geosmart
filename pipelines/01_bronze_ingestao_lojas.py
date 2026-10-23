import requests
from services.datalake_service import datalake

CNAES_ALVO = {
    "4511102": 16500, # Carros usados
    "4512902": 11000, # Consignação / Multimarcas
    "4541204": 5500,  # Motos usadas
    "4511101": 3500,  # Carros novos
    "4541203": 1800,  # Motos novas
    "4511104": 1200,  # Caminhões
    "4511106": 500    # Ônibus e micro-ônibus
}

def buscar_empresas_por_cnae(cnae: str, limite_desejado: int, cnpjs_vistos: set):
    """Realiza requisições paginadas na Minha Receita garantindo CNPJs únicos."""
    empresas_coletadas = []
    cursor = None
    url = "https://minhareceita.org/"
    headers = {"User-Agent": "BF-GeoSmart-DataLake/2.0"}
    
    while len(empresas_coletadas) < limite_desejado:
        params = {"cnae": cnae, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
            
        print(f"   -> Baixando página... (CNAE {cnae}: {len(empresas_coletadas)}/{limite_desejado} | Total Único: {len(cnpjs_vistos)})")
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)
            if response.status_code == 200:
                dados = response.json()
                lote = dados.get("data", [])
                
                if not lote:
                    break 
                    
                for emp in lote:
                    cnpj = emp.get("cnpj")
                    if cnpj and cnpj not in cnpjs_vistos:
                        cnpjs_vistos.add(cnpj)
                        empresas_coletadas.append(emp)
                    if len(empresas_coletadas) >= limite_desejado:
                        break
                
                cursor = dados.get("cursor")
                if not cursor:
                    break
            else:
                print(f"   -> Erro na API: Status {response.status_code}")
                break
        except Exception as e:
            print(f"   -> Erro na requisição: {e}")
            break

    return empresas_coletadas

def main():
    print("Iniciando extração de 40.000 lojas únicas via Minha Receita...\n")
    lojas_coletadas = []
    cnpjs_vistos = set()

    for cnae, limite in CNAES_ALVO.items():
        print(f"Buscando dados para o CNAE {cnae} (Meta: {limite} lojas inéditas)...")
        empresas = buscar_empresas_por_cnae(cnae, limite, cnpjs_vistos)
        
        if empresas:
            lojas_coletadas.extend(empresas)
            print(f"-> {len(empresas)} lojas inéditas adicionadas.\n")
        else:
            print("-> Nenhuma empresa encontrada.\n")

    if lojas_coletadas:
        total = len(lojas_coletadas)
        print(f"Extração concluída! {total} lojas únicas coletadas no total.")
        caminho_blob = "api_receita/lojas_raw.json"
        datalake.upload_json("bronze", caminho_blob, lojas_coletadas)
    else:
        print("Nenhum dado foi coletado.")

if __name__ == "__main__":
    main()