import argparse
import json
import os
import pandas as pd
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Mapeamento dos arquivos esperados nas respectivas camadas do Data Lake
LAYOUTS = {
    "gold": {
        "propostas": "propostas_gold",
        "metas": "metas_loja_gold",
        "colaboradores": "colaboradores_gold",
        "share": "historico_share_gold",
        "lojas": "lojas_gold",
    },
    "gerador": {
        "propostas": "propostas",
        "metas": "metas_loja",
        "colaboradores": "colaborador_bf",
        "share": "historico_marketing_share",
        "validacao": "validacao",
    },
    "sinteticos": {
        "propostas": "propostas",
        "metas": "metas_loja",
        "colaboradores": "colaboradores",
        "share": "historico_share",
    },
}
TODOS_NOMES = {n for lay in LAYOUTS.values() for n in lay.values()}

# Projeção de colunas necessárias da coleção de lojas (MongoDB)
CAMPOS_LOJA = {
    "_id": 0,
    "cnpj": 1,
    "razao_social": 1,
    "nome_fantasia": 1,
    "matriz_filial": 1,
    "gefin_id": 1,
    "tier_loja": 1,
    "porte": 1,
    "endereco_uf": 1,
    "endereco_municipio": 1,
}

def ler(caminho):
    """Função utilitária para leitura de arquivos JSON locais."""
    return json.loads(Path(caminho).read_text(encoding="utf-8"))

def achatar_propostas(brutas):
    """
    Transforma a estrutura hierárquica e aninhada do JSON de propostas
    em uma tabela relacional plana (DataFrame).
    """
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
    # Padronização de datas para Timezone Nulo (UTC)
    for col in ("data_proposta", "data_formalizacao", "data_pagamento"):
        p[col] = pd.to_datetime(p[col], utc=True, errors="coerce").dt.tz_localize(None)
    return p.drop(columns=["razao_social"], errors="ignore")

def validar(p, lojas, colab, ref):
    """
    Mecanismo de Data Quality.
    Gera uma trilha de auditoria verificando inconsistências relacionais e temporais.
    As linhas inválidas são separadas e não compõem os KPIs do dashboard.
    """
    fim_ref = pd.Timestamp(ref) + pd.Timedelta(days=1)
    gef_loja = lojas.drop_duplicates("cnpj").set_index("cnpj").gefin_id
    inativ = {
        d["_id"]: d["data_inativacao"][:7] for d in colab if d.get("data_inativacao")
    }
    gef_da_loja = p.cnpj_loja.map(gef_loja)
    ini = p.gefin_id.map(inativ)

    # Regras de negócio e consistência da base de dados
    checks = {
        "sem_cnpj_loja": p.cnpj_loja.isna() | (p.cnpj_loja == ""),
        "cnpj_nao_encontrado_em_lojas": p.cnpj_loja.notna() & gef_da_loja.isna(),
        "gefin_diferente_do_gefin_da_loja": gef_da_loja.notna()
        & (gef_da_loja != p.gefin_id),
        "inadimplencia_em_proposta_nao_convertida": (~p.proposta_convertida)
        & p.inadimplencia_percentual.notna(),
        "pago_sem_data_pagamento": (p.status_contrato == "PAGO")
        & p.data_pagamento.isna(),
        "pagamento_antes_da_formalizacao": p.data_pagamento.notna()
        & (p.data_pagamento < p.data_formalizacao),
        "proposta_apos_data_referencia": p.data_proposta >= fim_ref,
        "pagamento_apos_data_referencia": p.data_pagamento.notna()
        & (p.data_pagamento >= fim_ref),
        "proposta_de_gefin_inativo_apos_inativacao": ini.notna() & (p.ano_mes >= ini),
        "id_duplicado": p._id.duplicated(keep=False),
    }

    invalida = pd.Series(False, index=p.index)
    linhas = [{"verificacao": "propostas_lidas", "linhas": len(p)}]

    for nome, mascara in checks.items():
        mascara = mascara.fillna(False)
        linhas.append({"verificacao": nome, "linhas": int(mascara.sum())})
        invalida |= mascara

    linhas.append(
        {
            "verificacao": "propostas_excluidas_dos_numeros",
            "linhas": int(invalida.sum()),
        }
    )
    linhas.append(
        {"verificacao": "propostas_validas", "linhas": int((~invalida).sum())}
    )
    linhas.append(
        {
            "verificacao": "lojas_com_cnpj_duplicado",
            "linhas": int(lojas.cnpj.duplicated().sum()),
        }
    )

    return p[~invalida].copy(), pd.DataFrame(linhas)

def montar_dim_loja(lojas, ativas):
    """Cria a tabela de Dimensão Loja para o modelo Estrela."""
    cols = [
        "cnpj",
        "razao_social",
        "nome_fantasia",
        "matriz_filial",
        "gefin_id",
        "tier_loja",
        "porte",
        "endereco_uf",
        "endereco_municipio",
        "origem",
    ]
    d = (
        lojas[[c for c in cols if c in lojas.columns]]
        .drop_duplicates("cnpj")
        .rename(columns={"cnpj": "cnpj_loja"})
        .copy()
    )
    d["tem_proposta_no_periodo"] = d.cnpj_loja.isin(ativas)
    return d

def pegar(d, caminho, padrao=None):
    """Função utilitária para extrair valores de dicionários aninhados."""
    if caminho in d:
        return d[caminho]
    atual = d
    for parte in caminho.split("."):
        if not isinstance(atual, dict) or parte not in atual:
            return padrao
        atual = atual[parte]
    return atual

def montar_dim_gefin(colab):
    """Cria a tabela de Dimensão GEFIN extraindo a hierarquia comercial."""
    gef = [
        {
            "gefin_id": d["_id"],
            "gefin_nome": d.get("nome"),
            "gecom_id": pegar(d, "hierarquia.gecom_responsavel_id"),
            "sucom_id": pegar(d, "hierarquia.sucom_responsavel_id"),
            "municipio": pegar(d, "base_operacional.municipio"),
            "uf": pegar(d, "base_operacional.uf"),
            "ativo": d.get("ativo"),
            "data_inativacao": d.get("data_inativacao"),
        }
        for d in colab
        if d.get("tipo_colaborador") == "GEFIN"
    ]
    return pd.DataFrame(gef)

def montar_calendario(meses):
    """Gera a Dimensão de Tempo padrão para análises no Power BI."""
    datas = pd.date_range(
        pd.Timestamp(meses[0] + "-01"),
        pd.Timestamp(meses[-1] + "-01") + pd.offsets.MonthEnd(0),
    )
    c = pd.DataFrame({"data": datas})
    c["ano"], c["mes"], c["trimestre"] = (
        c.data.dt.year,
        c.data.dt.month,
        c.data.dt.quarter,
    )
    c["ano_mes"] = c.data.dt.strftime("%Y-%m")
    c["nome_mes"] = c.data.dt.strftime("%b")
    return c

def montar_fato_loja_mes(p, metas, meses, dim_loja):
    """
    Agrega os KPIs financeiros e o funil de conversão no nível granular da Loja.
    Cruza as propostas processadas com o valor esperado da base de metas.
    """
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
    pagos = p[p.status_contrato == "PAGO"]
    pag = (
        pagos.groupby(["cnpj_loja", "ano_mes_pagamento"])
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

    for c in (
        "n_propostas",
        "n_convertidas",
        "vgf_convertido",
        "producao_paga",
        "n_contratos_pagos",
    ):
        f[c] = f[c].fillna(0)

    f["n_propostas"], f["n_convertidas"], f["n_contratos_pagos"] = (
        f.n_propostas.astype(int),
        f.n_convertidas.astype(int),
        f.n_contratos_pagos.astype(int),
    )

    f["conversao"] = (f.n_convertidas / f.n_propostas).where(f.n_propostas > 0)
    f["atingimento"] = (f.producao_paga / f.meta_vgf).where(f.meta_vgf > 0)
    f = f.merge(dim_loja[["cnpj_loja", "gefin_id"]], on="cnpj_loja", how="left")
    f["mes_fechado"] = f.ano_mes.isin(meses[1:-2])

    return f.sort_values(["ano_mes", "cnpj_loja"]).reset_index(drop=True)

def montar_estat_loja(f):
    """
    Extração de Métricas de Estatística Descritiva (Média, Mediana e Desvio Padrão)
    sobre a produção de VGF das lojas, exigida pela disciplina do semestre.
    """
    base = f[f.mes_fechado & f.meta_vgf.notna()]
    g = base.groupby("cnpj_loja")
    e = g.agg(
        meses_com_meta=("ano_mes", "size"),
        producao_media=("producao_paga", "mean"),
        producao_mediana=("producao_paga", "median"),
        producao_desvio=("producao_paga", "std"),
        propostas_media=("n_propostas", "mean"),
        atingimento_medio=("atingimento", "mean"),
        atingimento_mediano=("atingimento", "median"),
    ).reset_index()

    e["meses_sem_producao"] = e.cnpj_loja.map(
        base.assign(zero=base.producao_paga == 0)
        .groupby("cnpj_loja")
        .zero.sum()
        .astype(int)
    )
    return e

def montar_fato_gefin_mes(f, share):
    """Agrega os resultados financeiros a nível de GEFIN e mescla com a performance de Market Share."""
    g = (
        f.groupby(["gefin_id", "ano_mes"])
        .agg(
            meta_vgf=("meta_vgf", "sum"),
            producao_paga=("producao_paga", "sum"),
            n_propostas=("n_propostas", "sum"),
            n_convertidas=("n_convertidas", "sum"),
            lojas_com_proposta=("n_propostas", lambda s: int((s > 0).sum())),
            mes_fechado=("mes_fechado", "first"),
        )
        .reset_index()
    )
    g["conversao"] = (g.n_convertidas / g.n_propostas).where(g.n_propostas > 0)
    g["atingimento"] = (g.producao_paga / g.meta_vgf).where(g.meta_vgf > 0)

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

# Operações com Azure Blob Storage e Leitura do Cosmos DB
def servico_blob():
    from azure.storage.blob import BlobServiceClient

    conexao = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conexao:
        raise SystemExit(
            "Aviso: Defina AZURE_STORAGE_CONNECTION_STRING no .env para realizar operações com o Blob Storage."
        )
    return BlobServiceClient.from_connection_string(conexao)

def ler_lojas_cosmos():
    """Conecta ao Azure Cosmos DB em modo apenas de leitura."""
    from pymongo import MongoClient

    uri = os.getenv("COSMOS_MONGO_URI") or os.getenv("COSMOS_MONGO_CONNECTION_STRING")
    if not uri:
        raise SystemExit(
            "Erro: Defina COSMOS_MONGO_URI no .env para a leitura da coleção de lojas."
        )

    banco, colecao = os.getenv("COSMOS_DB_NAME", "bf_geosmart"), os.getenv(
        "COSMOS_COLECAO_LOJAS", "lojas"
    )
    cliente = MongoClient(uri, serverSelectionTimeoutMS=20000)
    try:
        return list(cliente[banco][colecao].find({}, CAMPOS_LOJA))
    except Exception as erro:
        raise SystemExit(
            f"Falha na leitura da coleção '{colecao}' do Cosmos ({type(erro).__name__}). Valide se o IP local possui permissão de firewall no Azure."
        )
    finally:
        cliente.close()

def blob_existe(servico, container, caminho):
    try:
        return servico.get_blob_client(container=container, blob=caminho).exists()
    except Exception:
        return False

def layout_dos_arquivos(nomes):
    return next(
        (lay for lay, req in LAYOUTS.items() if set(req.values()) <= set(nomes)), None
    )

def descobrir_origens(servico, limite=200000):
    achados = []
    for c in servico.list_containers():
        pastas, n = {}, 0
        try:
            for b in servico.get_container_client(c.name).list_blobs():
                n += 1
                if n > limite:
                    break
                if b.name.endswith(".json"):
                    pasta, _, arq = b.name.rpartition("/")
                    pastas.setdefault(pasta, {})[arq[:-5]] = b.last_modified
        except Exception:
            continue
        for pasta, arqs in pastas.items():
            lay = layout_dos_arquivos(arqs)
            if lay:
                achados.append(
                    (c.name, pasta, lay, max(arqs[x] for x in LAYOUTS[lay].values()))
                )
    ordem = list(LAYOUTS)
    return sorted(achados, key=lambda x: (ordem.index(x[2]), -x[3].timestamp()))

def resumo_parcial(servico, limite=200000):
    linhas = []
    for c in servico.list_containers():
        pastas, total = {}, 0
        try:
            for blob in servico.get_container_client(c.name).list_blobs():
                total += 1
                if total > limite:
                    break
                pasta, _, arq = blob.name.rpartition("/")
                if arq.endswith(".json"):
                    pastas.setdefault(pasta, set()).add(arq[:-5])
        except Exception as erro:
            linhas.append(
                f"  {c.name}: Erro ao listar diretórios ({type(erro).__name__})"
            )
            continue
        linhas.append(f"  {c.name}: {total} arquivo(s)")
        for pasta, tem in pastas.items():
            linhas.append(f"      {pasta or '(raiz)'}: {sorted(tem)}")
    return linhas

def resolver_origem(servico, container, prefixo):
    if container and prefixo is not None:
        nomes = [
            n
            for n in TODOS_NOMES
            if blob_existe(servico, container, f"{prefixo}/{n}.json".strip("/"))
        ]
        lay = layout_dos_arquivos(nomes)
        if lay:
            return container, prefixo, lay
        print(
            f"Diretório {container}/{prefixo} não contém os arquivos padronizados. Iniciando varredura geral..."
        )

    achados = descobrir_origens(servico)
    if not achados:
        print("Estrutura atual do Data Lake:")
        print("\n".join(resumo_parcial(servico)))
        raise SystemExit(
            "\nErro: Nenhuma pasta com a estrutura esperada de JSONs analíticos foi localizada."
        )

    for c, pasta, lay, data in achados:
        print(
            f"  Diretório compatível localizado: {c}/{pasta}  [{lay}]  (Atualizado em {data:%d/%m/%Y %H:%M})"
        )
    c, pasta, lay, _ = achados[0]
    print(f"Definindo diretório principal de leitura: {c}/{pasta} [{lay}]")
    return c, pasta, lay

def ler_blob_json(servico, container, prefixo, nome):
    caminho = f"{prefixo}/{nome}.json".strip("/")
    try:
        dados = (
            servico.get_blob_client(container=container, blob=caminho)
            .download_blob()
            .readall()
        )
    except Exception as erro:
        raise SystemExit(
            f"Falha na leitura do objeto {container}/{caminho} no Azure Blob Storage ({type(erro).__name__})."
        )
    return json.loads(dados.decode("utf-8"))

def escolher_container_gold(servico, container_entrada):
    if os.getenv("PIPELINE_CONTAINER_GOLD"):
        return os.getenv("PIPELINE_CONTAINER_GOLD")
    if container_entrada in ("gold", "ouro"):
        return container_entrada
    try:
        existentes = {c.name for c in servico.list_containers()}
    except Exception:
        existentes = set()
    return next((n for n in ("gold", "ouro") if n in existentes), container_entrada)

def checar_prefixos(container_in, prefixo_in, container_out, prefixo_out):
    a, b = prefixo_in.strip("/"), prefixo_out.strip("/")
    if not b:
        raise SystemExit(
            "Aviso: A variável PIPELINE_PREFIXO_GOLD não pode estar vazia."
        )
    if container_in == container_out and (
        a == b or a.startswith(b + "/") or b.startswith(a + "/")
    ):
        raise SystemExit(
            f"Conflito de diretórios: O caminho de saída '{b}' não pode sobrescrever a origem '{a}'."
        )

def publicar_csv(servico, pasta, container, prefixo):
    from azure.storage.blob import ContentSettings

    for arquivo in sorted(pasta.glob("*.csv")):
        blob = servico.get_blob_client(
            container=container, blob=f"{prefixo.strip('/')}/{arquivo.name}"
        )
        try:
            with arquivo.open("rb") as f:
                blob.upload_blob(
                    f,
                    overwrite=True,
                    content_settings=ContentSettings(
                        content_type="text/csv; charset=utf-8"
                    ),
                )
        except Exception as erro:
            raise SystemExit(
                f"Erro na escrita do Azure Blob Storage: {container}/{prefixo.strip('/')} ({type(erro).__name__}). Os arquivos foram salvos apenas localmente."
            )
        print(
            f"Sucesso na publicação (Data Lake): {container}/{prefixo.strip('/')}/{arquivo.name}"
        )

def periodo_dos_dados(propostas, valid):
    if valid:
        return valid["meses"], valid["data_referencia"]
    ms = propostas.ano_mes.dropna().astype(str)
    meses = [str(m) for m in pd.period_range(ms.min(), ms.max(), freq="M")]
    return meses, str((pd.Timestamp.now("UTC") - pd.Timedelta(hours=3)).date())

def main():
    ap = argparse.ArgumentParser(
        description="Script de Extração e Agregação de Dados para Visualização (Power BI)"
    )
    ap.add_argument(
        "--fonte",
        choices=["auto", "arquivo", "blob"],
        default="auto",
        help="auto: prioriza leitura de disco local, alternando para o Blob Storage se necessário.",
    )
    ap.add_argument(
        "--entrada", help="Diretório local contendo os arquivos JSON de origem."
    )
    ap.add_argument(
        "--lojas",
        help="Arquivo JSON de cadastro de lojas (se ausente nos dados principais).",
    )
    ap.add_argument(
        "--lojas-fonte", choices=["auto", "origem", "arquivo", "cosmos"], default="auto"
    )
    ap.add_argument(
        "--env",
        default=".env",
        help="Caminho relativo para o arquivo de credenciais do sistema.",
    )
    ap.add_argument(
        "--saida",
        default="saida_powerbi",
        help="Diretório de destino para os modelos dimensionais (CSV).",
    )
    ap.add_argument(
        "--publicar-blob",
        action="store_true",
        help="Faz o upload automático do Star Schema gerado para a camada Gold do Azure.",
    )
    ap.add_argument(
        "--testar",
        action="store_true",
        help="Verifica as conexões e mapeamentos de diretórios sem executar as transformações analíticas.",
    )
    ap.add_argument(
        "--mes",
        help="Filtra a agregação de relatórios para o período especificado (ex: 2026-08).",
    )
    ap.add_argument(
        "--pt-br",
        action="store_true",
        help="Formata os arquivos CSV de saída com delimitador ponto e vírgula e decimal em vírgula.",
    )
    a = ap.parse_args()

    if load_dotenv:
        if a.env != ".env" and not Path(a.env).exists():
            raise SystemExit(f"Arquivo de ambiente não encontrado: {a.env}")
        load_dotenv(a.env)

    saida = Path(a.saida)
    pasta_local = Path(a.entrada) if a.entrada else Path("saida_json")
    fonte = a.fonte

    if fonte == "auto":
        fonte = (
            "arquivo"
            if (
                a.entrada
                or layout_dos_arquivos(
                    [f.stem for f in pasta_local.glob("*.json")]
                    if pasta_local.exists()
                    else []
                )
            )
            else "blob"
        )
    print(f"Origem definida de dados transacionais: {fonte}")

    servico = (
        servico_blob() if (fonte == "blob" or a.publicar_blob or a.testar) else None
    )
    c_in, p_in, layout = None, "", None

    if fonte == "blob":
        c_in, p_in, layout = resolver_origem(
            servico,
            os.getenv("AZURE_STORAGE_CONTAINER"),
            os.getenv("AZURE_STORAGE_PREFIX"),
        )
    else:
        layout = (
            layout_dos_arquivos([f.stem for f in pasta_local.glob("*.json")])
            if pasta_local.exists()
            else None
        )
        if layout is None:
            raise SystemExit(
                f"Aviso: Os JSONs base não foram encontrados no diretório '{pasta_local}'."
            )

    nomes = LAYOUTS[layout]
    lojas_fonte = a.lojas_fonte
    if lojas_fonte == "auto":
        lojas_fonte = (
            "arquivo" if a.lojas else ("origem" if "lojas" in nomes else "cosmos")
        )

    if lojas_fonte == "cosmos":
        print("Iniciando extração da dimensão Lojas na API do Cosmos DB...")
        lojas = pd.DataFrame(ler_lojas_cosmos())
    elif lojas_fonte == "origem":
        print("Iniciando leitura das lojas diretamente dos arquivos base...")
        lojas = pd.DataFrame(
            ler_blob_json(servico, c_in, p_in, nomes["lojas"])
            if fonte == "blob"
            else ler(pasta_local / f"{nomes['lojas']}.json")
        )
    else:
        candidatos = (
            [Path(a.lojas)]
            if a.lojas
            else [
                pasta_local / "lojas_usadas.json",
                pasta_local / "lojas_simuladas.json",
            ]
        )
        lojas_arq = next((c for c in candidatos if c.exists()), None)
        if lojas_arq is None:
            raise SystemExit(f"Erro: Cadastro de Lojas não encontrado localmente.")
        lojas = pd.DataFrame(ler(lojas_arq))

    if lojas.empty or not {"cnpj", "gefin_id"} <= set(lojas.columns):
        raise SystemExit(
            "Erro Crítico: O DataFrame das lojas foi instanciado sem as chaves relacionais 'cnpj' e 'gefin_id'."
        )

    c_out = escolher_container_gold(servico, c_in) if servico else None
    p_out = os.getenv("PIPELINE_PREFIXO_GOLD", "powerbi")

    if fonte == "blob" and (a.publicar_blob or a.testar):
        checar_prefixos(c_in, p_in, c_out, p_out)

    if a.testar:
        print("Testes de Conectividade do Sistema concluídos com sucesso.")
        return

    chaves = [k for k in nomes if k not in ("lojas",)]
    dados = {}
    for k in chaves:
        dados[k] = (
            ler_blob_json(servico, c_in, p_in, nomes[k])
            if fonte == "blob"
            else ler(pasta_local / f"{nomes[k]}.json")
        )

    print("\nIniciando modelagem da Fato de Propostas...")
    colab, metas, share = (
        dados["colaboradores"],
        pd.DataFrame(dados["metas"]),
        pd.DataFrame(dados["share"]),
    )
    bruto = achatar_propostas(dados.pop("propostas"))
    meses, ref = periodo_dos_dados(bruto, dados.get("validacao"))

    print("\nRealizando verificações de Data Quality na base bruta...")
    p, qualidade = validar(bruto, lojas, colab, ref)
    del bruto

    if p.empty:
        saida.mkdir(parents=True, exist_ok=True)
        qualidade.to_csv(
            saida / "qualidade_dados.csv", index=False, encoding="utf-8-sig"
        )
        raise SystemExit(
            "Execução Interrompida: Nenhuma proposta passou na validação da tabela de Data Quality."
        )

    print("Consolidando as tabelas e KPIs finais do modelo Estrela...")
    dim_loja = montar_dim_loja(lojas, set(p.cnpj_loja))
    dim_gefin = montar_dim_gefin(colab)
    fato_loja_mes = montar_fato_loja_mes(p, metas, meses, dim_loja)
    estat_loja = montar_estat_loja(fato_loja_mes)
    fato_gefin_mes = montar_fato_gefin_mes(fato_loja_mes, share)

    tabelas = {
        "fato_proposta": p,
        "fato_loja_mes": fato_loja_mes,
        "fato_gefin_mes": fato_gefin_mes,
        "estat_loja": estat_loja,
        "dim_loja": dim_loja,
        "dim_gefin": dim_gefin,
        "dim_calendario": montar_calendario(meses),
        "qualidade_dados": qualidade,
    }

    destino, prefixo_gold = saida, p_out
    if a.mes:
        if a.mes not in meses:
            raise SystemExit(
                f"O período inserido {a.mes} não consta nos limites disponíveis da base ({meses[0]} a {meses[-1]})."
            )
        destino, prefixo_gold = (
            saida / f"mes_{a.mes}",
            f"{p_out.strip('/')}/mes_{a.mes}",
        )
        for nome in ("fato_proposta", "fato_loja_mes", "fato_gefin_mes"):
            tabelas[nome] = tabelas[nome][tabelas[nome].ano_mes == a.mes]
        tabelas.pop("estat_loja")

    destino.mkdir(parents=True, exist_ok=True)
    sep, dec = (";", ",") if a.pt_br else (",", ".")

    print("\nSalvando extratos .csv localmente...")
    for nome, df in tabelas.items():
        df.to_csv(
            destino / f"{nome}.csv",
            index=False,
            sep=sep,
            decimal=dec,
            encoding="utf-8-sig",
            date_format="%Y-%m-%d %H:%M:%S" if nome == "fato_proposta" else "%Y-%m-%d",
        )

    if a.publicar_blob:
        if servico is None:
            raise SystemExit(
                "Aviso: Configuração necessária de AZURE_STORAGE_CONNECTION_STRING."
            )
        print("\nSincronizando tabelas com a Nuvem (Camada Gold/Power BI)...")
        publicar_csv(servico, destino, c_out, prefixo_gold)

if __name__ == "__main__":
    main()
