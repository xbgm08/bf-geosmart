import argparse
import calendar
import json
import math
import os
import random
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
from services.datalake_service import datalake

SEED_PADRAO = 20260926
OUTPUT_PADRAO = "saida_json"
INICIO_PADRAO = "2025-01"
FUSO_BRASIL = timezone(timedelta(hours=-3))

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
PESO_CATEGORIA = [0.45, 0.35, 0.20]
MULT_VALOR_CATEGORIA = {"LEVE": 1.0, "MOTOS": 0.25, "PESADOS": 2.5}
AJUSTE_CONV_CATEGORIA = {"LEVE": 0.0, "MOTOS": 0.01, "PESADOS": -0.012}
AJUSTE_INAD_CATEGORIA = {"LEVE": 0.0, "MOTOS": 0.1, "PESADOS": 0.2}
PRAZOS = [24, 36, 48, 60]
PESO_PRAZO = {
    "LEVE": [0.15, 0.30, 0.30, 0.25],
    "MOTOS": [0.35, 0.35, 0.20, 0.10],
    "PESADOS": [0.10, 0.25, 0.30, 0.35],
}
TIPOS_OPERACAO = ["CDC", "LEASING"]
PERFIS_SHARE = [
    "estavel_alto",
    "estavel_baixo",
    "crescimento",
    "queda",
    "oscilante",
    "recuperacao",
]
SAZONALIDADE = {
    1: 0.96,
    2: 0.94,
    3: 1.00,
    4: 1.00,
    5: 1.02,
    6: 1.00,
    7: 1.02,
    8: 1.03,
    9: 1.00,
    10: 1.05,
    11: 1.07,
    12: 1.10,
}
TENDENCIA_MENSAL = 0.003

RANK_CONHECIDO = {
    "PREMIUM": 0,
    "PLATINA": 0,
    "OURO": 0,
    "A": 0,
    "1": 0,
    "ALTO": 0,
    "ALTA": 0,
    "GRANDE": 0,
    "DEMAIS": 0,
    "PRATA": 1,
    "B": 1,
    "2": 1,
    "MEDIO": 1,
    "MEDIA": 1,
    "EPP": 1,
    "EMPRESA DE PEQUENO PORTE": 1,
    "BRONZE": 2,
    "C": 2,
    "3": 2,
    "BAIXO": 2,
    "BAIXA": 2,
    "PEQUENO": 2,
    "PEQUENA": 2,
    "MICRO EMPRESA": 2,
    "MICROEMPRESA": 2,
    "ME": 2,
    "D": 3,
    "4": 3,
    "MICRO": 3,
}

DISTRIBUICAO_LOJAS_POR_GEFIN = [
    (14, 1),
    (16, 1),
    (17, 2),
    (18, 2),
    (19, 4),
    (20, 9),
    (21, 12),
    (22, 9),
    (23, 36),
    (24, 32),
    (25, 35),
    (26, 33),
    (27, 44),
    (28, 56),
    (29, 58),
    (30, 40),
    (31, 56),
    (32, 49),
    (33, 46),
    (34, 45),
    (35, 28),
    (36, 23),
    (37, 18),
    (38, 13),
    (39, 14),
    (40, 9),
    (41, 7),
    (42, 3),
    (43, 5),
    (44, 4),
    (45, 4),
    (47, 1),
    (49, 1),
]

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

def dinheiro(valor):
    return round(max(0.0, float(valor)), 2)

def clip(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))

def fmt_data(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:00Z")

def salvar_json_local(caminho: Path, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(dados, list) and len(dados) > 20000:
        texto = json.dumps(
            dados, ensure_ascii=False, separators=(",", ":"), default=str
        )
    else:
        texto = json.dumps(dados, ensure_ascii=False, indent=2, default=str)
    caminho.write_text(texto, encoding="utf-8")

def lista_meses(inicio, ate):
    ano, mes = map(int, inicio.split("-"))
    ano_f, mes_f = map(int, ate.split("-"))
    meses = []
    while (ano, mes) <= (ano_f, mes_f):
        meses.append(f"{ano}-{mes:02d}")
        mes += 1
        if mes == 13:
            ano, mes = ano + 1, 1
    return meses

def poisson(rng, lam):
    """
    Função matemática para Distribuição de Poisson.
    Utilizada para simular a probabilidade 
    do número de propostas de crédito (eventos) que uma loja vai gerar 
    num determinado mês, com base no seu histórico (lambda).
    """
    if lam <= 0:
        return 0
    if lam < 30:
        limite, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= rng.random()
            if p <= limite:
                return k
            k += 1
    return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))

def sortear(rng, opcoes, pesos):
    r, acum = rng.random() * sum(pesos), 0.0
    for opcao, peso in zip(opcoes, pesos):
        acum += peso
        if r <= acum:
            return opcao
    return opcoes[-1]

def _norm(valor):
    texto = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode()
    return texto.upper().strip()

def efeitos_por_valor(valores, ordem_manual=None):
    distintos = sorted({_norm(v) for v in valores if v not in (None, "")})
    if ordem_manual:
        ordem = [_norm(x) for x in ordem_manual if _norm(x)]
        ordem += [v for v in distintos if v not in ordem]
    elif distintos and all(v in RANK_CONHECIDO for v in distintos):
        ordem = sorted(distintos, key=lambda v: (RANK_CONHECIDO[v], v))
    else:
        ordem = distintos
    k = len(ordem)
    efeitos = {v: (1 - 2 * i / (k - 1) if k > 1 else 0.0) for i, v in enumerate(ordem)}
    return efeitos, ordem

# Colaboradores
def gerar_colaboradores_bf(rng):
    """Gera a hierarquia comercial unificada (SUCOM, GECOM, GEFIN) mantendo a seed original."""
    documentos = []
    for numero in range(1, 11):
        documentos.append(
            {
                "_id": f"PES-SUCOM-{numero:04d}",
                "tipo_colaborador": "SUCOM",
                "matricula": f"SU{numero:06d}",
                "nome": f"Superintendência Comercial {numero:02d}",
                "email": f"sucom{numero:02d}@bfgeosmart.local",
                "cargo": "SUCOM",
                "ativo": True,
            }
        )
    for numero in range(1, 81):
        sucom_numero = ((numero * 7 - 1) % 10) + 1
        documentos.append(
            {
                "_id": f"PES-GECOM-{numero:04d}",
                "tipo_colaborador": "GECOM",
                "matricula": f"GE{numero:06d}",
                "nome": f"Gerência Comercial Regional {numero:03d}",
                "email": f"gecom{numero:03d}@bfgeosmart.local",
                "cargo": "GECOM",
                "hierarquia": {"sucom_responsavel_id": f"PES-SUCOM-{sucom_numero:04d}"},
                "ativo": rng.random() > 0.03,
            }
        )
    for numero in range(1, 701):
        gecom_numero = ((numero * 13 - 1) % 80) + 1
        sucom_numero = ((gecom_numero * 7 - 1) % 10) + 1
        uf, municipio, longitude, latitude = CIDADES[(numero - 1) % len(CIDADES)]
        documentos.append(
            {
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
            }
        )
    return documentos

def indexar_gefins(colaboradores, meses, rng):
    info = {}
    for doc in colaboradores:
        if doc["tipo_colaborador"] != "GEFIN":
            continue
        inativ_idx = None
        if not doc["ativo"]:
            inativ_idx = rng.randint(max(1, len(meses) // 3), max(1, len(meses) - 1))
            doc["data_inativacao"] = f"{meses[inativ_idx]}-01"
        info[doc["_id"]] = {
            "gecom": doc["hierarquia"]["gecom_responsavel_id"],
            "sucom": doc["hierarquia"]["sucom_responsavel_id"],
            "uf": doc["base_operacional"]["uf"],
            "inativ_idx": inativ_idx,
        }
    return info

# Share dos GEFINs
def gerar_historico_marketing_share(rng, gefin_ids, meses):
    n = len(meses)
    perfis = [PERFIS_SHARE[i % len(PERFIS_SHARE)] for i in range(len(gefin_ids))]
    rng.shuffle(perfis)
    registros, serie_por_gefin = [], {}
    for gefin_id, perfil in zip(gefin_ids, perfis):
        base_alto, base_baixo = rng.uniform(0.66, 0.84), rng.uniform(0.06, 0.20)
        base_cresc, base_queda = rng.uniform(0.10, 0.68), rng.uniform(0.32, 0.80)
        base_rec, base_osc = rng.uniform(0.15, 0.70), rng.uniform(0.12, 0.78)
        anterior, serie = None, []
        for i, mes in enumerate(meses):
            t = i / (n - 1) if n > 1 else 0.0
            if perfil == "estavel_alto":
                share = base_alto + rng.uniform(-0.04, 0.04)
            elif perfil == "estavel_baixo":
                share = base_baixo + rng.uniform(-0.03, 0.03)
            elif perfil == "crescimento":
                share = base_cresc + 0.20 * t + rng.uniform(-0.025, 0.025)
            elif perfil == "queda":
                share = base_queda - 0.22 * t + rng.uniform(-0.025, 0.025)
            elif perfil == "recuperacao":
                share = (
                    base_rec - 0.09 * max(0.0, 1 - t / 0.4) + rng.uniform(-0.02, 0.02)
                )
            else:
                share = base_osc + rng.uniform(-0.10, 0.10)
            share = round(max(0.0, min(1.0, share)), 4)
            registros.append(
                {
                    "_id": f"SHARE-{gefin_id}-{mes}",
                    "gefin_id": gefin_id,
                    "mes_referencia": mes,
                    "share": share,
                    "share_anterior": anterior,
                    "variacao_share": (
                        None if anterior is None else round(share - anterior, 4)
                    ),
                    "perfil_comercial": perfil,
                    "origem": "gerada",
                }
            )
            serie.append(share)
            anterior = share
        serie_por_gefin[gefin_id] = serie
    return registros, serie_por_gefin

# Leitura e Preparo de Lojas
def carregar_lojas_cosmos():
    uri = os.getenv("COSMOS_MONGO_URI") or os.getenv("COSMOS_MONGO_CONNECTION_STRING")
    if not uri:
        raise RuntimeError(
            "Defina COSMOS_MONGO_URI no .env para ler as lojas do Cosmos DB."
        )
    banco = os.getenv("COSMOS_DB_NAME", "bf_geosmart")
    colecao = os.getenv("COSMOS_COLECAO_LOJAS", "lojas")
    cliente = MongoClient(uri, serverSelectionTimeoutMS=20000)
    try:
        return list(cliente[banco][colecao].find({}, CAMPOS_LOJA))
    except Exception as erro:
        raise SystemExit(
            f"Erro ao ler a coleção '{colecao}' do Cosmos ({type(erro).__name__}). "
            "Verifique o .env ou use --local-only."
        )
    finally:
        cliente.close()


def carregar_lojas_arquivo(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def gerar_lojas_simuladas(rng, colaboradores):
    gefins = [d for d in colaboradores if d["tipo_colaborador"] == "GEFIN"]
    contagens = [n for n, qtd in DISTRIBUICAO_LOJAS_POR_GEFIN for _ in range(qtd)]
    rng.shuffle(contagens)
    lojas, usados = [], set()
    for i, doc in enumerate(gefins):
        lon, lat = doc["base_operacional"]["coordinates"]
        for _ in range(contagens[i % len(contagens)]):
            while True:
                cnpj = "".join(rng.choice("0123456789") for _ in range(14))
                if cnpj not in usados:
                    usados.add(cnpj)
                    break
            numero = len(lojas) + 1
            lojas.append(
                {
                    "_id": cnpj,
                    "cnpj": cnpj,
                    "razao_social": f"LOJA SIMULADA {numero:05d} LTDA",
                    "nome_fantasia": f"Loja Simulada {numero:05d}",
                    "matriz_filial": rng.choices(["MATRIZ", "FILIAL"], [0.7, 0.3])[0],
                    "porte": rng.choices(
                        ["DEMAIS", "EMPRESA DE PEQUENO PORTE", "MICRO EMPRESA"],
                        [0.15, 0.25, 0.60],
                    )[0],
                    "gefin_id": doc["_id"],
                    "tier_loja": rng.choices(
                        ["OURO", "PRATA", "BRONZE"], [0.15, 0.35, 0.50]
                    )[0],
                    "endereco_uf": doc["base_operacional"]["uf"],
                    "endereco_municipio": doc["base_operacional"]["municipio"],
                    "localizacao": {
                        "type": "Point",
                        "coordinates": [
                            round(lon + rng.uniform(-0.35, 0.35), 6),
                            round(lat + rng.uniform(-0.30, 0.30), 6),
                        ],
                    },
                    "geocodificado_real": False,
                    "origem": "simulada",
                }
            )
    return lojas

def preparar_lojas(lojas_brutas, gefin_info, rng, args):
    """
    Filtra as lojas válidas do banco de dados e calcula a sua intensidade de vendas.
    Inclui um mecanismo de desduplicação de CNPJs (utilizando um Set) para 
    evitar problemas de chaves duplicadas no Cosmos DB durante a geração de metas.
    """
    validas, ignoradas, cnpjs_vistos = [], 0, set()
    for loja in lojas_brutas:
        cnpj = loja.get("cnpj")
        if cnpj and cnpj not in cnpjs_vistos and loja.get("gefin_id") in gefin_info:
            cnpjs_vistos.add(cnpj)
            validas.append(loja)
        else:
            ignoradas += 1
    ef_tier, ordem_tier = efeitos_por_valor(
        [l.get("tier_loja") for l in validas], args.tier_ordem
    )
    ef_porte, ordem_porte = efeitos_por_valor(
        [l.get("porte") for l in validas], args.porte_ordem
    )
    if not validas:
        raise SystemExit(
            "Nenhuma loja válida encontrada com 'cnpj' e 'gefin_id' válidos."
        )
    print(
        f" -> Lojas lidas: {len(lojas_brutas)} | Válidas: {len(validas)} | Ignoradas: {ignoradas}"
    )
    print(f" -> Ordem de tier (melhor -> pior): {ordem_tier}")
    print(f" -> Ordem de porte (melhor -> pior): {ordem_porte}")

    ativas = []
    for loja in validas:
        e_tier = ef_tier.get(_norm(loja.get("tier_loja", "")), 0.0)
        e_porte = ef_porte.get(_norm(loja.get("porte", "")), 0.0)
        p_ativa = min(
            0.95, max(0.02, args.fracao_ativa * (1 + 0.10 * e_tier + 0.05 * e_porte))
        )
        if rng.random() >= p_ativa:
            continue
        intensidade = (
            min(rng.lognormvariate(0.0, 0.8), 7.0)
            * (1 + 0.15 * e_tier)
            * (1 + 0.10 * e_porte)
        )
        ativas.append(
            {
                "cnpj": loja["cnpj"],
                "razao_social": loja.get("razao_social", ""),
                "gefin": loja["gefin_id"],
                "uf": loja.get("endereco_uf") or gefin_info[loja["gefin_id"]]["uf"],
                "e_tier": e_tier,
                "e_porte": e_porte,
                "intens": max(intensidade, 0.02),
                "cresc": rng.gauss(0.0, 0.012),
                "qual": rng.gauss(0.0, 0.02),
            }
        )
    media = sum(l["intens"] for l in ativas) / max(1, len(ativas))
    for loja in ativas:
        loja["intens"] *= args.media_prop_mes / media
    resumo = {
        "lojas_lidas": len(lojas_brutas),
        "lojas_validas": len(validas),
        "lojas_ignoradas": ignoradas,
        "lojas_ativas": len(ativas),
        "ordem_tier": ordem_tier,
        "ordem_porte": ordem_porte,
    }
    return ativas, resumo


# Propostas e Metas
def gerar_uma_proposta(rng, loja, info, hab, ano, mes, ultimo_dia, agora):
    categoria = sortear(rng, CATEGORIAS, PESO_CATEGORIA)
    novo = rng.random() < 0.5
    tipo_veiculo = "NOVO" if novo else "USADO"
    ano_fab = ano - rng.randint(0, 1) if novo else ano - rng.randint(2, 10)
    valor_bem = dinheiro(
        rng.lognormvariate(11.0, 0.42)
        * MULT_VALOR_CATEGORIA[categoria]
        * (1.20 if novo else 0.85)
    )
    entrada = dinheiro(valor_bem * rng.uniform(0.20, 0.45))
    financiado = dinheiro(valor_bem - entrada)
    ltv = financiado / valor_bem if valor_bem else 0.7
    prazo = sortear(rng, PRAZOS, PESO_PRAZO[categoria])
    prazo_idx = PRAZOS.index(prazo)
    operacao = rng.choice(TIPOS_OPERACAO)

    dt_prop = datetime(
        ano, mes, rng.randint(1, ultimo_dia), rng.randint(8, 18), rng.randint(0, 59)
    )
    if dt_prop > agora:
        dt_prop = agora.replace(second=0, microsecond=0)

    p_conv = clip(
        0.67
        + 0.015 * loja["e_tier"]
        + 0.008 * loja["e_porte"]
        + loja["qual"]
        + hab["conv"]
        - 0.10 * (ltv - 0.675)
        + AJUSTE_CONV_CATEGORIA[categoria]
        - 0.004 * prazo_idx
        + (0.01 if novo else -0.008),
        0.30,
        0.92,
    )
    convertida = rng.random() < p_conv

    paga, status, dt_form, dt_pag, inad = False, "NAO_CONVERTIDA", None, None, None
    if convertida:
        inad = clip(
            3.4
            + 2.5 * (ltv - 0.675)
            + 0.12 * prazo_idx
            + (0.15 if not novo else 0.0)
            + AJUSTE_INAD_CATEGORIA[categoria]
            - 0.12 * loja["e_tier"]
            - 0.05 * loja["e_porte"]
            + hab["inad"]
            + rng.gauss(0.0, 0.7),
            0.2,
            12.0,
        )
        inad = round(inad, 2)
        dt_form = min(
            dt_prop
            + timedelta(
                days=rng.randint(0, 7),
                hours=rng.randint(0, 5),
                minutes=rng.randint(0, 59),
            ),
            agora,
        )
        status = "ATIVO"
        p_pago = clip(0.92 - 0.02 * prazo_idx - 0.015 * (inad - 4.0), 0.60, 0.98)
        if rng.random() < p_pago:
            dt_pag = dt_form + timedelta(
                days=rng.randint(3, 40), hours=rng.randint(0, 8)
            )
            if dt_pag <= agora:
                paga, status = True, "PAGO"
            else:
                dt_pag = None

    return {
        "_id": None,
        "origem": "gerada",
        "gefin_id": loja["gefin"],
        "gecom_id": info["gecom"],
        "sucom_id": info["sucom"],
        "cnpj_loja": loja["cnpj"],
        "razao_social": loja["razao_social"],
        "ano_mes": f"{ano}-{mes:02d}",
        "data_proposta": fmt_data(dt_prop),
        "veiculo": {
            "categoria": categoria,
            "tipo": tipo_veiculo,
            "ano_fabricacao": ano_fab,
            "valor_bem": valor_bem,
        },
        "condicoes_solicitadas": {
            "valor_entrada": entrada,
            "valor_financiado": financiado,
            "prazo_meses": prazo,
        },
        "contrato": {
            "numero_contrato": None,
            "data_formalizacao": fmt_data(dt_form) if dt_form else None,
            "data_pagamento": fmt_data(dt_pag) if dt_pag else None,
            "ano_mes_pagamento": dt_pag.strftime("%Y-%m") if dt_pag else None,
            "valor_contrato_vgf": financiado if convertida else 0.0,
            "tipo_operacao": operacao,
            "status_contrato": status,
        },
        "indicadores": {
            "proposta_convertida": convertida,
            "contrato_pago": paga,
            "inadimplencia_percentual": inad,
        },
    }

def gerar_propostas_e_metas(rng, lojas, gefin_info, share_series, meses, agora):
    """
    Motor central de geração sintética.
    Modelo baseado no histórico da loja, introduzindo choques macroeconómicos 
    por UF e sazonalidade para as disciplinas de Analytics.
    Gera o facto de 'Metas' e as 'Propostas' já atreladas ao CNPJ da loja.
    """
    choque_nac = [math.exp(rng.gauss(0.0, 0.025)) for _ in meses]
    ufs = sorted({l["uf"] for l in lojas})
    choque_uf = {uf: [math.exp(rng.gauss(0.0, 0.035)) for _ in meses] for uf in ufs}
    habilidade = defaultdict(lambda: {"conv": 0.0, "inad": 0.0})
    for gid in gefin_info:
        habilidade[gid] = {"conv": rng.gauss(0.0, 0.02), "inad": rng.gauss(0.0, 0.20)}

    propostas, metas = [], []
    mes_atual = agora.strftime("%Y-%m")
    for mi, mes in enumerate(meses):
        ano, mm = int(mes[:4]), int(mes[5:])
        dias_mes = calendar.monthrange(ano, mm)[1]
        ultimo_dia = min(dias_mes, agora.day) if mes == mes_atual else dias_mes
        frac_mes = ultimo_dia / dias_mes
        base_meta = SAZONALIDADE[mm] * (1 + TENDENCIA_MENSAL) ** mi
        for loja in lojas:
            info = gefin_info[loja["gefin"]]
            if info["inativ_idx"] is not None and mi >= info["inativ_idx"]:
                continue
            lam_meta = loja["intens"] * base_meta * (1 + loja["cresc"]) ** mi
            share = share_series[loja["gefin"]][mi]
            lam = (
                lam_meta
                * choque_nac[mi]
                * choque_uf[loja["uf"]][mi]
                * (0.6 + 0.8 * share)
            )
            meta_vgf = lam_meta * 0.55 * 44500.0 * rng.uniform(0.92, 1.10)
            metas.append(
                {
                    "_id": f"META-{loja['cnpj']}-{mes}",
                    "cnpj_loja": loja["cnpj"],
                    "gefin_id": loja["gefin"],
                    "ano_mes": mes,
                    "meta_vgf": round(meta_vgf, 2),
                    "meta_propostas": max(
                        1, int(round(lam_meta * rng.uniform(0.9, 1.15)))
                    ),
                    "meta_origem": "gerada",
                }
            )
            for _ in range(poisson(rng, lam * frac_mes)):
                propostas.append(
                    gerar_uma_proposta(
                        rng,
                        loja,
                        info,
                        habilidade[loja["gefin"]],
                        ano,
                        mm,
                        ultimo_dia,
                        agora,
                    )
                )
    propostas.sort(key=lambda p: p["data_proposta"])
    for seq, p in enumerate(propostas, start=1):
        ano_p = p["data_proposta"][:4]
        p["_id"] = f"PROP-{ano_p}-{seq:08d}"
        if p["indicadores"]["proposta_convertida"]:
            p["contrato"]["numero_contrato"] = f"CTR-{ano_p}-{seq:08d}"
    return propostas, metas

def main():
    parser = argparse.ArgumentParser(
        description="Gerador Sintético BF GeoSmart v2 (Camada Silver)"
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Salva apenas em disco local sem subir para o Data Lake",
    )
    parser.add_argument(
        "--salvar-local",
        action="store_true",
        help="Além de subir ao Data Lake, salva cópia em saida_json/",
    )
    parser.add_argument(
        "--lojas-fonte",
        choices=["auto", "cosmos", "arquivo", "simulado"],
        default="auto",
    )
    parser.add_argument(
        "--lojas-arquivo", help="Caminho de arquivo JSON local de lojas"
    )
    parser.add_argument(
        "--inicio", default=INICIO_PADRAO, help="Primeiro mês AAAA-MM (padrão: 2025-01)"
    )
    parser.add_argument(
        "--ate", default=None, help="Último mês AAAA-MM (padrão: mês atual)"
    )
    parser.add_argument("--hoje", default=None, help="Data de referência AAAA-MM-DD")
    parser.add_argument("--fracao-ativa", type=float, default=0.60)
    parser.add_argument("--media-prop-mes", type=float, default=1.0)
    parser.add_argument("--tier-ordem", default=None)
    parser.add_argument("--porte-ordem", default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    args.tier_ordem = args.tier_ordem.split(",") if args.tier_ordem else None
    args.porte_ordem = args.porte_ordem.split(",") if args.porte_ordem else None

    print("1. Inicializando gerador de dados sintéticos (v2)...")
    load_dotenv(override=True)
    semente = (
        args.seed if args.seed is not None else int(os.getenv("SEED", str(SEED_PADRAO)))
    )
    agora = (
        datetime.strptime(args.hoje, "%Y-%m-%d").replace(hour=23, minute=59)
        if args.hoje
        else datetime.now(FUSO_BRASIL).replace(tzinfo=None, second=0, microsecond=0)
    )
    ate = args.ate or agora.strftime("%Y-%m")
    meses = lista_meses(args.inicio, ate)
    output_dir = Path(os.getenv("OUTPUT_DIR", OUTPUT_PADRAO))

    print("2. Gerando Colaboradores e Histórico de Marketing Share...")
    colaboradores = gerar_colaboradores_bf(random.Random(semente))
    info = indexar_gefins(colaboradores, meses, random.Random(semente + 11))
    gefin_ids = sorted(info)
    share_registros, share_series = gerar_historico_marketing_share(
        random.Random(semente + 21), gefin_ids, meses
    )

    # Resolução automática da fonte de lojas
    fonte = args.lojas_fonte
    if fonte == "auto":
        tem_cosmos = bool(
            os.getenv("COSMOS_MONGO_URI") or os.getenv("COSMOS_MONGO_CONNECTION_STRING")
        )
        if args.lojas_arquivo:
            fonte = "arquivo"
        elif args.local_only or not tem_cosmos:
            fonte = "simulado"
        else:
            fonte = "cosmos"
    args.lojas_fonte = fonte

    print(f"3. Carregando base de lojas (Fonte: {fonte})...")
    if fonte == "cosmos":
        lojas_brutas = carregar_lojas_cosmos()
    elif fonte == "arquivo":
        if not args.lojas_arquivo:
            raise SystemExit("Informe --lojas-arquivo com o JSON das lojas.")
        lojas_brutas = carregar_lojas_arquivo(args.lojas_arquivo)
    else:
        lojas_brutas = gerar_lojas_simuladas(random.Random(semente + 51), colaboradores)
        if args.local_only or args.salvar_local:
            salvar_json_local(output_dir / "lojas_simuladas.json", lojas_brutas)

    lojas, resumo_lojas = preparar_lojas(
        lojas_brutas, info, random.Random(semente + 31), args
    )

    print(f"4. Gerando Propostas e Metas ({meses[0]} até {meses[-1]})...")
    propostas, metas = gerar_propostas_e_metas(
        random.Random(semente + 41), lojas, info, share_series, meses, agora
    )

    # Mapeamento oficial para a Camada Silver do repositório bf-geosmart
    arquivos_silver = {
        "dados_sinteticos/colaboradores.json": colaboradores,
        "dados_sinteticos/propostas.json": propostas,
        "dados_sinteticos/historico_share.json": share_registros,
        "dados_sinteticos/metas_loja.json": metas,
    }

    if args.local_only or args.salvar_local:
        print(f"\nSalvando cópias locais na pasta '{output_dir}'...")
        for caminho_blob, dados in arquivos_silver.items():
            nome_arquivo = Path(caminho_blob).name
            caminho_local = output_dir / nome_arquivo
            salvar_json_local(caminho_local, dados)
            print(f" -> Arquivo local salvo: {caminho_local} ({len(dados)} registros)")

    if args.local_only:
        print("\nModo --local-only concluído com sucesso!")
        return

    print("\n5. Enviando dados para a camada Silver no Azure Data Lake...")
    for caminho_blob, dados in arquivos_silver.items():
        datalake.upload_json("silver", caminho_blob, dados)
        print(
            f" -> silver/{caminho_blob} enviado com sucesso! ({len(dados)} registros)"
        )

    print("\nPipeline de dados sintéticos (v2) concluído com sucesso!")

if __name__ == "__main__":
    main()