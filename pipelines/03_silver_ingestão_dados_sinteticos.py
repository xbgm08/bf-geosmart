import os
import random
from datetime import datetime, timezone
from dotenv import load_dotenv
from services.datalake_service import datalake

MESES = [f"2026-{mes:02d}" for mes in range(1, 13)]
SEED_PADRAO = 20260926
CIDADES = [
    ("SP", "São Paulo", -46.6333, -23.5505),
    ("SP", "Campinas", -47.0608, -22.9099),
    ("RJ", "Rio de Janeiro", -43.1729, -22.9068),
    ("MG", "Belo Horizonte", -43.9378, -19.9208),
    ("PR", "Curitiba", -49.2643, -25.4296),
    ("RS", "Porto Alegre", -51.2177, -30.0346),
    ("DF", "Brasília", -47.8825, -15.7942),
    ("BA", "Salvador", -38.5014, -12.9777),
    ("PE", "Recife", -34.8770, -8.0476),
    ("GO", "Goiânia", -49.2532, -16.6869),
]
CATEGORIAS = ["LEVE", "MOTOS", "PESADOS"]
TIPOS_VEICULO = ["NOVO", "USADO"]
TIPOS_OPERACAO = ["CDC", "LEASING"]
PERFIS_SHARE = [
    "estavel_alto",
    "estavel_baixo",
    "crescimento",
    "queda",
    "oscilante",
    "recuperacao",
]

def dinheiro(valor):
    return round(max(0.0, float(valor)), 2)


def gerar_colaboradores_bf(rng):
    """Gera a hierarquia comercial unificada (SUCOM, GECOM, GEFIN)."""
    documentos = []
    
    # Gerar SUCOMs
    for numero in range(1, 11):
        documentos.append({
            "_id": f"PES-SUCOM-{numero:04d}",
            "tipo_colaborador": "SUCOM",
            "matricula": f"SU{numero:06d}",
            "nome": f"Superintendência Comercial {numero:02d}",
            "email": f"sucom{numero:02d}@bfgeosmart.local",
            "cargo": "SUCOM",
            "ativo": True,
        })
        
    # Gerar GECOMs
    for numero in range(1, 81):
        sucom_numero = ((numero * 7 - 1) % 10) + 1
        documentos.append({
            "_id": f"PES-GECOM-{numero:04d}",
            "tipo_colaborador": "GECOM",
            "matricula": f"GE{numero:06d}",
            "nome": f"Gerência Comercial Regional {numero:03d}",
            "email": f"gecom{numero:03d}@bfgeosmart.local",
            "cargo": "GECOM",
            "hierarquia": {"sucom_responsavel_id": f"PES-SUCOM-{sucom_numero:04d}"},
            "ativo": rng.random() > 0.03,
        })
        
    # Gerar GEFINs
    for numero in range(1, 701):
        gecom_numero = ((numero * 13 - 1) % 80) + 1
        sucom_numero = ((gecom_numero * 7 - 1) % 10) + 1
        uf, municipio, longitude, latitude = CIDADES[(numero - 1) % len(CIDADES)]
        
        documentos.append({
            "_id": f"PES-GEFIN-{numero:04d}",
            "tipo_colaborador": "GEFIN",
            "matricula": f"GF{numero:06d}",
            "nome": f"GEFIN {municipio} {numero:03d}",
            "email": f"gefin{numero:04d}@bfgeosmart.local",
            "cargo": "GEFIN",
            "hierarquia": {
                "sucom_responsavel_id": f"PES-SUCOM-{sucom_numero:04d}",
                "gecom_responsavel_id": f"PES-GECOM-{gecom_numero:04d}",
            },
            "base_operacional": {
                "type": "Point",
                "coordinates": [
                    round(longitude + rng.uniform(-0.08, 0.08), 6),
                    round(latitude + rng.uniform(-0.08, 0.08), 6),
                ],
                "municipio": municipio,
                "uf": uf,
            },
            "ativo": rng.random() > 0.04,
        })
    return documentos


def gerar_propostas(rng):
    """Gera as propostas brutas ancoradas aos gerentes."""
    propostas, sequencia = [], 1
    pesos = [1.0 + ((numero * 17) % 9) / 10 for numero in range(1, 701)]
    total_peso = sum(pesos)
    
    for mes_index, mes in enumerate(MESES):
        quantidade_mes = 900 + ((mes_index * 137) % 420)
        for _ in range(quantidade_mes):
            sorteio, acumulado, gefin_numero = rng.uniform(0, total_peso), 0.0, 1
            for indice, peso in enumerate(pesos, start=1):
                acumulado += peso
                if sorteio <= acumulado:
                    gefin_numero = indice
                    break
                    
            gecom_numero = ((gefin_numero * 13 - 1) % 80) + 1
            sucom_numero = ((gecom_numero * 7 - 1) % 10) + 1
            
            valor_bem = dinheiro(rng.lognormvariate(11.0, 0.42))
            entrada = dinheiro(valor_bem * rng.uniform(0.20, 0.45))
            financiado = dinheiro(valor_bem - entrada)
            convertida = rng.random() < rng.uniform(0.54, 0.82)
            paga = convertida and rng.random() < rng.uniform(0.73, 0.97)
            data = f"{mes}-{rng.randint(1, 28):02d}T{rng.randint(8, 18):02d}:{rng.randint(0, 59):02d}:00Z"
            status = "NAO_CONVERTIDA" if not convertida else ("PAGO" if paga else "ATIVO")
            contrato = None if not convertida else f"CTR-2026-{sequencia:08d}"
            
            propostas.append({
                "_id": f"PROP-2026-{sequencia:08d}",
                "gefin_id": f"PES-GEFIN-{gefin_numero:04d}",
                "gecom_id": f"PES-GECOM-{gecom_numero:04d}",
                "sucom_id": f"PES-SUCOM-{sucom_numero:04d}",
                "data_proposta": data,
                "veiculo": {
                    "categoria": rng.choice(CATEGORIAS),
                    "tipo": rng.choice(TIPOS_VEICULO),
                    "ano_fabricacao": rng.randint(2017, 2026),
                    "valor_bem": valor_bem,
                },
                "condicoes_solicitadas": {
                    "valor_entrada": entrada,
                    "valor_financiado": financiado,
                    "prazo_meses": rng.choice([24, 36, 48, 60]),
                },
                "contrato": {
                    "numero_contrato": contrato,
                    "data_formalizacao": data if contrato else None,
                    "valor_contrato_vgf": financiado if contrato else 0.0,
                    "tipo_operacao": rng.choice(TIPOS_OPERACAO),
                    "status_contrato": status,
                },
                "indicadores": {
                    "proposta_convertida": convertida,
                    "contrato_pago": paga,
                    "inadimplencia_percentual": round(rng.uniform(0.4, 7.5), 2),
                },
            })
            sequencia += 1
            
    return propostas


def gerar_historico_marketing_share(rng):
    """Gera o histórico de performance consolidada por GEFIN."""
    registros = []
    for numero in range(1, 701):
        perfil = PERFIS_SHARE[(numero * 5 - 1) % len(PERFIS_SHARE)]
        base = rng.uniform(0.08, 0.78)
        anterior = None
        
        for mes_index, mes in enumerate(MESES):
            if perfil == "estavel_alto":
                share = rng.uniform(0.62, 0.88)
            elif perfil == "estavel_baixo":
                share = rng.uniform(0.04, 0.22)
            elif perfil == "crescimento":
                share = base + mes_index * 0.018 + rng.uniform(-0.025, 0.025)
            elif perfil == "queda":
                share = base - mes_index * 0.020 + rng.uniform(-0.025, 0.025)
            elif perfil == "recuperacao":
                share = base - max(0, 5 - mes_index) * 0.018 + rng.uniform(-0.02, 0.02)
            else:
                share = base + rng.uniform(-0.10, 0.10)
                
            share = round(max(0.0, min(1.0, share)), 4)
            
            registros.append({
                "_id": f"SHARE-PES-GEFIN-{numero:04d}-{mes}",
                "gefin_id": f"PES-GEFIN-{numero:04d}",
                "mes_referencia": mes,
                "share": share,
                "share_anterior": anterior,
                "variacao_share": None if anterior is None else round(share - anterior, 4),
                "perfil_comercial": perfil,
            })
            anterior = share
            
    return registros


def main():
    print("Iniciando geração de dados sintéticos...")
    load_dotenv(override=True)
    rng = random.Random(int(os.getenv("SEED", str(SEED_PADRAO))))

    print("Gerando Colaboradores...")
    colaboradores = gerar_colaboradores_bf(rng)
    
    print("Gerando Propostas...")
    propostas = gerar_propostas(rng)
    
    print("Gerando Histórico de Share...")
    historico = gerar_historico_marketing_share(rng)

    arquivos_upload = {
        "dados_sinteticos/colaboradores.json": colaboradores,
        "dados_sinteticos/propostas.json": propostas,
        "dados_sinteticos/historico_share.json": historico,
    }

    print("\nEnviando dados para a camada Bronze no Azure Data Lake...")
    for caminho_blob, dados in arquivos_upload.items():
        datalake.upload_json("bronze", caminho_blob, dados)
        print(f"-> {caminho_blob} enviado com sucesso! ({len(dados) if isinstance(dados, list) else 1} registros)")

    print("\nPipeline de dados sintéticos concluído com sucesso!")


if __name__ == "__main__":
    main()