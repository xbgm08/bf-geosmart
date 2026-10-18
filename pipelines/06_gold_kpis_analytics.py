import os
import json
import numpy as np
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from bson import ObjectId
from services.datalake_service import datalake

def carregar_dados_silver():
    """Lê os arquivos brutos do Data Lake (Camada Silver ou Gold inicial)."""
    print("1. Lendo dados consolidados do Data Lake...")

    colaboradores = datalake.download_json(
        "gold", "modelagem_final/colaboradores_gold.json"
    )
    lojas = pd.DataFrame(
        datalake.download_json("gold", "modelagem_final/lojas_gold.json")
    )
    propostas_brutas = datalake.download_json(
        "silver", "dados_sinteticos/propostas.json"
    )
    metas = pd.DataFrame(
        datalake.download_json("silver", "dados_sinteticos/metas_loja.json")
    )
    share = pd.DataFrame(
        datalake.download_json("silver", "dados_sinteticos/historico_share.json")
    )

    return colaboradores, lojas, propostas_brutas, metas, share

def achatar_propostas(brutas):
    """Transforma o JSON de propostas num DataFrame plano para o Pandas."""
    p = pd.json_normalize(brutas)
    p = p.rename(
        columns={
            "veiculo.categoria": "categoria",
            "veiculo.tipo": "tipo_veiculo",
            "veiculo.ano_fabricacao": "ano_fabricacao",
            "veiculo.valor_bem": "valor_bem",
            "condicoes_solicitadas.valor_entrada": "valor_entrada",
            "condicoes_solicitadas.valor_financiado": "valor_financiado",
            "condicoes_solicitadas.prazo_meses": "prazo_meses",
            "contrato.numero_contrato": "numero_contrato",
            "contrato.data_formalizacao": "data_formalizacao",
            "contrato.data_pagamento": "data_pagamento",
            "contrato.ano_mes_pagamento": "ano_mes_pagamento",
            "contrato.valor_contrato_vgf": "valor_contrato_vgf",
            "contrato.tipo_operacao": "tipo_operacao",
            "contrato.status_contrato": "status_contrato",
            "indicadores.proposta_convertida": "proposta_convertida",
            "indicadores.contrato_pago": "contrato_pago",
            "indicadores.inadimplencia_percentual": "inadimplencia_percentual",
        }
    )
    for col in ("data_proposta", "data_formalizacao", "data_pagamento"):
        p[col] = pd.to_datetime(p[col], utc=True, errors="coerce").dt.tz_localize(None)
    return p.drop(columns=["razao_social"], errors="ignore")

def extrair_meses_validos(p):
    """Identifica o período ativo (ignora meses de ponta incompleta)."""
    ms = p.ano_mes.dropna().astype(str)
    meses = [str(m) for m in pd.period_range(ms.min(), ms.max(), freq="M")]
    # Remove o primeiro e os dois últimos meses para a estatística (meses incompletos)
    return meses, meses[1:-2]

def montar_kpis_loja_mes(p, metas, meses_fechados, lojas):
    """Agrega os KPIs no nível da Loja."""
    print("2. Calculando KPIs por Loja...")
    prop = (
        p.groupby(["cnpj_loja", "ano_mes"])
        .agg(
            n_propostas=("_id", "size"),
            n_convertidas=("proposta_convertida", "sum"),
            vgf_convertido=("valor_contrato_vgf", "sum"),
            inadimplencia_media=("inadimplencia_percentual", "mean"),
        )
        .reset_index()
    )
    pag = (
        p[p.status_contrato == "PAGO"]
        .groupby(["cnpj_loja", "ano_mes_pagamento"])
        .agg(
            producao_paga=("valor_contrato_vgf", "sum"),
            n_contratos_pagos=("_id", "size"),
        )
        .reset_index()
        .rename(columns={"ano_mes_pagamento": "ano_mes"})
    )

    m = metas[["cnpj_loja", "ano_mes", "meta_vgf", "meta_propostas"]]
    f = m.merge(prop, on=["cnpj_loja", "ano_mes"], how="outer").merge(
        pag, on=["cnpj_loja", "ano_mes"], how="outer"
    )

    cols_preencher = [
        "n_propostas",
        "n_convertidas",
        "vgf_convertido",
        "producao_paga",
        "n_contratos_pagos",
    ]
    f[cols_preencher] = f[cols_preencher].fillna(0).astype(int)

    f["conversao"] = (
        (f.n_convertidas / f.n_propostas).where(f.n_propostas > 0).fillna(0.0)
    )
    f["atingimento"] = (f.producao_paga / f.meta_vgf).where(f.meta_vgf > 0).fillna(0.0)
    f["mes_fechado"] = f.ano_mes.isin(meses_fechados)

    # Associa o GEFIN atual da loja
    f = f.merge(
        lojas[["cnpj", "gefin_id"]].rename(columns={"cnpj": "cnpj_loja"}),
        on="cnpj_loja",
        how="left",
    )

    return f.sort_values(["ano_mes", "cnpj_loja"]).reset_index(drop=True)

def montar_kpis_gefin_mes(f, share):
    """Agrega os KPIs no nível do GEFIN."""
    print("3. Consolidando KPIs por Gestor (GEFIN)...")
    g = (
        f.groupby(["gefin_id", "ano_mes"])
        .agg(
            meta_vgf=("meta_vgf", "sum"),
            producao_paga=("producao_paga", "sum"),
            n_propostas=("n_propostas", "sum"),
            n_convertidas=("n_convertidas", "sum"),
            lojas_ativas=("n_propostas", lambda s: int((s > 0).sum())),
            mes_fechado=("mes_fechado", "first"),
        )
        .reset_index()
    )
    g["conversao"] = (
        (g.n_convertidas / g.n_propostas).where(g.n_propostas > 0).fillna(0.0)
    )
    g["atingimento"] = (g.producao_paga / g.meta_vgf).where(g.meta_vgf > 0).fillna(0.0)

    s = share.rename(columns={"mes_referencia": "ano_mes"})
    s = s[
        [
            c
            for c in (
                "gefin_id",
                "ano_mes",
                "share",
                "variacao_share",
                "perfil_comercial",
            )
            if c in s.columns
        ]
    ]

    return g.merge(s, on=["gefin_id", "ano_mes"], how="left")

def calcular_estatisticas_loja(f):
    """Extrai média, mediana e desvio padrão para o K-Means."""
    print("4. Extraindo Métricas Estatísticas (VGF Médio)...")
    base = f[f.mes_fechado & f.meta_vgf.notna()]
    e = (
        base.groupby("cnpj_loja")
        .agg(
            meses_com_meta=("ano_mes", "size"),
            producao_media=("producao_paga", "mean"),
            producao_mediana=("producao_paga", "median"),
            producao_desvio=("producao_paga", "std"),
        )
        .reset_index()
    )

    # Substitui NaN no desvio padrão (lojas com 1 mês só) por 0
    e["producao_desvio"] = e["producao_desvio"].fillna(0.0)
    return e

def normalizar_snapshot(valor):
    """Converte identificadores BSON para valores aceitos em JSON."""
    if isinstance(valor, ObjectId):
        return str(valor)
    if isinstance(valor, dict):
        return {chave: normalizar_snapshot(item) for chave, item in valor.items()}
    if isinstance(valor, list):
        return [normalizar_snapshot(item) for item in valor]
    return valor

def salvar_cosmos_db(kpis_loja, kpis_gefin, estatisticas):
    """Grava as coleções novas e atualiza as lojas no Cosmos DB."""
    print("5. Sincronizando com o Azure Cosmos DB...")
    uri = os.getenv("COSMOS_MONGO_URI") or os.getenv("COSMOS_MONGO_CONNECTION_STRING")
    if not uri:
        raise ValueError("Defina COSMOS_MONGO_URI no arquivo .env.")

    banco = os.getenv("COSMOS_DB_NAME", "bf_geosmart")
    cliente = MongoClient(uri, serverSelectionTimeoutMS=20000)
    db = cliente[banco]

    # Limpa coleções de KPI caso o script seja rodado novamente
    db["kpis_loja_mes"].drop()
    db["kpis_gefin_mes"].drop()

    # Prepara JSON
    docs_loja = normalizar_snapshot(
        kpis_loja.replace({np.nan: None}).to_dict("records")
    )
    docs_gefin = normalizar_snapshot(
        kpis_gefin.replace({np.nan: None}).to_dict("records")
    )

    print(f" -> Inserindo {len(docs_loja)} documentos em kpis_loja_mes...")
    db["kpis_loja_mes"].insert_many(docs_loja)

    print(f" -> Inserindo {len(docs_gefin)} documentos em kpis_gefin_mes...")
    db["kpis_gefin_mes"].insert_many(docs_gefin)

    # O PyMongo adiciona _id como ObjectId aos dicionários após a inserção.
    # Normaliza novamente antes de enviar os mesmos documentos ao Data Lake.
    docs_loja = normalizar_snapshot(docs_loja)
    docs_gefin = normalizar_snapshot(docs_gefin)

    # UpdateOne para adicionar 'producao_media' direto no documento da Loja
    print(" -> Atualizando as métricas estatísticas dentro da coleção 'lojas'...")
    operacoes = []
    for _, row in estatisticas.iterrows():
        operacoes.append(
            UpdateOne(
                {"cnpj": row["cnpj_loja"]},
                {
                    "$set": {
                        "estatisticas": {
                            "producao_media": row["producao_media"],
                            "producao_mediana": row["producao_mediana"],
                            "producao_desvio": row["producao_desvio"],
                            "meses_com_meta": row["meses_com_meta"],
                        }
                    }
                },
            )
        )

    # Executa o Bulk Write em lotes de 1000 para não estourar o limite de RU/s
    lote_size = 1000
    for i in range(0, len(operacoes), lote_size):
        db["lojas"].bulk_write(operacoes[i : i + lote_size])

    cliente.close()
    print("Sincronização com o banco de dados concluída!")

    return docs_loja, docs_gefin

def main():
    load_dotenv(override=True)

    # 1. Carga
    colab, lojas, prop_brutas, metas, share = carregar_dados_silver()

    # 2. Processamento
    p = achatar_propostas(prop_brutas)
    meses_totais, meses_fechados = extrair_meses_validos(p)

    kpis_loja = montar_kpis_loja_mes(p, metas, meses_fechados, lojas)
    kpis_gefin = montar_kpis_gefin_mes(kpis_loja, share)
    estatisticas = calcular_estatisticas_loja(kpis_loja)

    # 3. Gravação no Cosmos DB
    docs_loja, docs_gefin = salvar_cosmos_db(kpis_loja, kpis_gefin, estatisticas)

    # 4. Backup Snapshot no Data Lake (Camada Gold)
    print("6. Salvando snapshots de backup no Data Lake (gold/analytics)...")
    datalake.upload_json("gold", "analytics/kpis_loja_mes.json", docs_loja)
    datalake.upload_json("gold", "analytics/kpis_gefin_mes.json", docs_gefin)

    print("\nPipeline 06 executada com sucesso. Os KPIs agora vivem no Cosmos DB!")

if __name__ == "__main__":
    main()
