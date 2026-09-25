from services.datalake_service import datalake

def capitalizar_texto(texto: str) -> str:
    """Transforma 'NOME DA EMPRESA' em 'Nome Da Empresa' lidando com valores nulos."""
    if not texto:
        return ""
    return texto.strip().title()

def limpar_dados_lojas(dados_raw: list) -> list:
    """Aplica as regras de negócio e padronização da camada Silver."""
    lojas_silver = []
    
    for loja in dados_raw:
        # Filtrando apenas empresas ATIVAS (Código 2 na Receita Federal)
        if loja.get("situacao_cadastral") != 2:
            continue
        
        # Descartando MEIs
        if loja.get("opcao_pelo_mei") is True:
            continue
            
        # Padronizando o Nome Fantasia e Razão Social.
        razao_social = capitalizar_texto(loja.get("razao_social"))
        nome_fantasia = capitalizar_texto(loja.get("nome_fantasia"))
        
        # Dando preferência ao Nome Fantasia para ficar mais intuitivo
        nome_exibicao = nome_fantasia if nome_fantasia else razao_social

        # Montando o dicionário apenas com o que importa
        loja_limpa = {
            "cnpj": loja.get("cnpj"),
            "razao_social": razao_social,
            "nome_fantasia": nome_exibicao,
            "matriz_filial": capitalizar_texto(loja.get("descricao_identificador_matriz_filial")),
            "porte": capitalizar_texto(loja.get("porte")),
            "cnae_codigo": str(loja.get("cnae_fiscal")),
            "cnae_descricao": capitalizar_texto(loja.get("cnae_fiscal_descricao")),
            "data_abertura": loja.get("data_inicio_atividade"),
            "telefone_principal": f"{loja.get('ddd_telefone_1', '')}".strip(),
            "telefone_secundario": f"{loja.get('ddd_telefone_2', '')}".strip(),
            "endereco_uf": loja.get("uf", "").upper(),
            "endereco_municipio": capitalizar_texto(loja.get("municipio")),
            "endereco_bairro": capitalizar_texto(loja.get("bairro")),
            "endereco_logradouro": capitalizar_texto(loja.get("logradouro")),
            "endereco_numero": loja.get("numero", ""),
            "endereco_complemento": capitalizar_texto(loja.get("complemento")),
            "endereco_cep": loja.get("cep", "")
        }
        
        lojas_silver.append(loja_limpa)
        
    return lojas_silver

def main():
    print("Iniciando processamento da camada Silver...")
    
    # Extração
    print("Baixando dados brutos da camada Bronze...")
    dados_raw = datalake.download_json("bronze", "api_receita/lojas_raw.json")
    print(f"-> {len(dados_raw)} registros brutos carregados.")
    
    # Transformação
    print("Aplicando regras de limpeza e padronização...")
    dados_silver = limpar_dados_lojas(dados_raw)
    
    # Carga
    qtd_removidas = len(dados_raw) - len(dados_silver)
    print(f"-> {len(dados_silver)} lojas ativas padronizadas.")
    print(f"-> {qtd_removidas} lojas inativas/baixadas foram descartadas.")
    
    print("Enviando dados tratados para a camada Silver no Azure...")
    datalake.upload_json("silver", "api_receita/lojas_silver.json", dados_silver)
    
    print("Pipeline Silver concluído com sucesso!")

if __name__ == "__main__":
    main()