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
from services.datalake_service import datalake

SEED_PADRAO = 20260926
OUTPUT_PADRAO = "saida_json"
INICIO_PADRAO = "2025-01"
FUSO_BRASIL = timezone(timedelta(hours=-3))

# Coordenadas das capitais das 27 UFs (Município, Longitude, Latitude)
CAPITAIS_UF = {
    "SP": ("São Paulo", -46.6333, -23.5505),
    "RJ": ("Rio de Janeiro", -43.1729, -22.9068),
    "ES": ("Vitória", -40.3128, -20.3155),
    "MG": ("Belo Horizonte", -43.9378, -19.9208),
    "PR": ("Curitiba", -49.2643, -25.4296),
    "SC": ("Florianópolis", -48.5480, -27.5954),
    "RS": ("Porto Alegre", -51.2177, -30.0346),
    "DF": ("Brasília", -47.8825, -15.7942),
    "GO": ("Goiânia", -49.2532, -16.6869),
    "MT": ("Cuiabá", -56.0979, -15.6014),
    "MS": ("Campo Grande", -54.6201, -20.4697),
    "BA": ("Salvador", -38.5014, -12.9777),
    "SE": ("Aracaju", -37.0731, -10.9472),
    "AL": ("Maceió", -35.7350, -9.6658),
    "PE": ("Recife", -34.8770, -8.0476),
    "PB": ("João Pessoa", -34.8641, -7.1195),
    "RN": ("Natal", -35.2094, -5.7945),
    "CE": ("Fortaleza", -38.5267, -3.7319),
    "PI": ("Teresina", -42.8016, -5.0920),
    "MA": ("São Luís", -44.3068, -2.5307),
    "PA": ("Belém", -48.4902, -1.4558),
    "AM": ("Manaus", -60.0217, -3.1190),
    "TO": ("Palmas", -48.3243, -10.1844),
    "RO": ("Porto Velho", -63.9039, -8.7619),
    "AC": ("Rio Branco", -67.8249, -9.9754),
    "AP": ("Macapá", -51.0694, 0.0349),
    "RR": ("Boa Vista", -60.6758, 2.8235),
}

# 10 SUCOMs regionalizadas cobrindo todas as 27 UFs
REGIOES_SUCOM = [
    {"id": "PES-SUCOM-0001", "num": 1, "nome": "SUCOM 01 - São Paulo", "sede_uf": "SP", "ufs": ["SP"], "qtd_gecoms": 18},
    {"id": "PES-SUCOM-0003", "num": 3, "nome": "SUCOM 02 - Rio de Janeiro & Espírito Santo", "sede_uf": "RJ", "ufs": ["RJ", "ES"], "qtd_gecoms": 6},
    {"id": "PES-SUCOM-0004", "num": 4, "nome": "SUCOM 03 - Minas Gerais", "sede_uf": "MG", "ufs": ["MG"], "qtd_gecoms": 7},
    {"id": "PES-SUCOM-0005", "num": 5, "nome": "SUCOM 04 - Paraná & Santa Catarina", "sede_uf": "PR", "ufs": ["PR", "SC"], "qtd_gecoms": 7},
    {"id": "PES-SUCOM-0006", "num": 6, "nome": "SUCOM 05 - Rio Grande do Sul", "sede_uf": "RS", "ufs": ["RS"], "qtd_gecoms": 5},
    {"id": "PES-SUCOM-0007", "num": 7, "nome": "SUCOM 06 - Centro-Oeste", "sede_uf": "DF", "ufs": ["DF", "GO", "MT", "MS"], "qtd_gecoms": 7},
    {"id": "PES-SUCOM-0002", "num": 2, "nome": "SUCOM 07 - Bahia", "sede_uf": "BA", "ufs": ["BA"], "qtd_gecoms": 6},
    {"id": "PES-SUCOM-0008", "num": 8, "nome": "SUCOM 08 - Nordeste Sul (SE/AL/PE)", "sede_uf": "PE", "ufs": ["SE", "AL", "PE"], "qtd_gecoms": 6},
    {"id": "PES-SUCOM-0009", "num": 9, "nome": "SUCOM 09 - Nordeste Norte (PB/RN/CE/PI/MA)", "sede_uf": "RN", "ufs": ["PB", "RN", "CE", "PI", "MA"], "qtd_gecoms": 9},
    {"id": "PES-SUCOM-0010", "num": 10, "nome": "SUCOM 10 - Norte", "sede_uf": "AM", "ufs": ["PA", "AM", "TO", "RO", "AC", "AP", "RR"], "qtd_gecoms": 9},
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
    "MICRO": 3
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
    """
    Gera SUCOM, GECOM e GEFIN com coordinates [lon, lat], municipio e uf coerentes com a sua região.
    """
    documentos = []
    gecom_seq = 1

    # Gera 10 SUCOMs e 80 GECOMs com Lat/Long e UF
    for reg in REGIOES_SUCOM:
        mun_sede, lon_sede, lat_sede = CAPITAIS_UF[reg["sede_uf"]]
        documentos.append({
            "_id": reg["id"],
            "tipo_colaborador": "SUCOM",
            "matricula": f"SU{reg['num']:06d}",
            "nome": reg["nome"],
            "email": f"sucom{reg['num']:02d}@bfgeosmart.local",
            "cargo": "SUCOM",
            "base_operacional": {
                "type": "Point",
                "coordinates": [round(lon_sede, 6), round(lat_sede, 6)],
                "municipio": mun_sede,
                "uf": reg["sede_uf"],
                "ufs_cobertura": reg["ufs"],
            },
            "ativo": True,
        })

        ufs_regiao = reg["ufs"]
        for i in range(reg["qtd_gecoms"]):
            uf_gecom = ufs_regiao[i % len(ufs_regiao)]
            mun_g, lon_g, lat_g = CAPITAIS_UF[uf_gecom]
            gecom_id = f"PES-GECOM-{gecom_seq:04d}"

            documentos.append({
                "_id": gecom_id,
                "tipo_colaborador": "GECOM",
                "matricula": f"GE{gecom_seq:06d}",
                "nome": f"GECOM {uf_gecom} Regional {gecom_seq:03d}",
                "email": f"gecom{gecom_seq:03d}@bfgeosmart.local",
                "cargo": "GECOM",
                "hierarquia": {"sucom_responsavel_id": reg["id"]},
                "base_operacional": {
                    "type": "Point",
                    "coordinates": [
                        round(lon_g + rng.uniform(-0.10, 0.10), 6),
                        round(lat_g + rng.uniform(-0.10, 0.10), 6),
                    ],
                    "municipio": mun_g,
                    "uf": uf_gecom,
                },
                "ativo": True,
            })
            gecom_seq += 1

    # Gera 700 GEFINs estritamente dentro da mesma UF do seu GECOM pai
    gecoms_criados = [d for d in documentos if d["tipo_colaborador"] == "GECOM"]
    for numero in range(1, 701):
        gecom_pai = gecoms_criados[(numero - 1) % len(gecoms_criados)]
        uf_gf = gecom_pai["base_operacional"]["uf"]
        mun_gf, lon_base, lat_base = CAPITAIS_UF[uf_gf]
        sucom_pai_id = gecom_pai["hierarquia"]["sucom_responsavel_id"]

        documentos.append({
            "_id": f"PES-GEFIN-{numero:04d}",
            "tipo_colaborador": "GEFIN",
            "matricula": f"GF{numero:06d}",
            "nome": f"GEFIN {mun_gf} {numero:03d} - {uf_gf}",
            "email": f"gefin{numero:04d}@bfgeosmart.local",
            "cargo": "GEFIN",
            "hierarquia": {
                "sucom_responsavel_id": sucom_pai_id,
                "gecom_responsavel_id": gecom_pai["_id"],
            },
            "base_operacional": {
                "type": "Point",
                "coordinates": [
                    round(lon_base + rng.uniform(-0.15, 0.15), 6),
                    round(lat_base + rng.uniform(-0.15, 0.15), 6),
                ],
                "municipio": mun_gf,
                "uf": uf_gf,
            },
            "ativo": rng.random() > 0.04,
        })

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

def carregar_e_vincular_lojas_silver(colaboradores, serie_por_gefin, meses, rng):
    """
    Lê 'api_receita/lojas_silver.json', agrupa as lojas por UF e ordena por
    Município + Bairro para que cada GEFIN receba um bloco geograficamente concentrado
    de lojas da sua mesma UF (evitando espalhamento entre cidades distantes).
    """
    lojas_silver = datalake.download_json("silver", "api_receita/lojas_silver.json")

    docs_gefin_por_uf = defaultdict(list)
    todos_docs_gefin = []
    for doc in colaboradores:
        if doc["tipo_colaborador"] == "GEFIN" and doc.get("ativo", True):
            uf_doc = doc["base_operacional"]["uf"]
            docs_gefin_por_uf[uf_doc].append(doc)
            todos_docs_gefin.append(doc)

    for doc in colaboradores:
        if doc["tipo_colaborador"] == "GEFIN":
            uf_doc = doc["base_operacional"]["uf"]
            if not docs_gefin_por_uf[uf_doc]:
                docs_gefin_por_uf[uf_doc].append(doc)

    # Agrupa lojas únicas por UF
    lojas_por_uf = defaultdict(list)
    cnpjs_vistos = set()
    for loja in lojas_silver:
        cnpj = loja.get("cnpj")
        if not cnpj or cnpj in cnpjs_vistos:
            continue
        cnpjs_vistos.add(cnpj)
        uf_loja = str(loja.get("endereco_uf", "SP")).strip().upper()
        lojas_por_uf[uf_loja].append(loja)

    lojas_enriquecidas = []
    ultimos_12_meses = meses[-12:] if len(meses) >= 12 else meses

    for uf_loja, lista_lojas_uf in lojas_por_uf.items():
        # Ordena por município e bairro para manter lojas vizinhas no mesmo GEFIN
        lista_lojas_uf.sort(key=lambda x: (str(x.get("endereco_municipio", "")), str(x.get("endereco_bairro", ""))))
        gefins_uf = docs_gefin_por_uf.get(uf_loja) or todos_docs_gefin
        qtd_gefins = len(gefins_uf)
        total_uf = len(lista_lojas_uf)

        for idx, loja in enumerate(lista_lojas_uf):
            # Fatia contígua: lojas da mesma cidade ficam no mesmo GEFIN
            idx_gefin = min(qtd_gefins - 1, int(idx * qtd_gefins / max(1, total_uf)))
            doc_gefin = gefins_uf[idx_gefin]
            gefin_escolhido = doc_gefin["_id"]

            # Atualiza o município do GEFIN com o município real das lojas que ele atende
            if loja.get("endereco_municipio"):
                doc_gefin["base_operacional"]["municipio"] = loja["endereco_municipio"]
                num_str = gefin_escolhido.split("-")[-1]
                doc_gefin["nome"] = f"GEFIN {loja['endereco_municipio']} {num_str} - {uf_loja}"

            porte_norm = _norm(loja.get("porte", ""))
            if "DEMAIS" in porte_norm or "GRANDE" in porte_norm:
                tier = rng.choices(["OURO", "PRATA", "BRONZE"], [0.45, 0.40, 0.15])[0]
            elif "PEQUENO" in porte_norm or "EPP" in porte_norm:
                tier = rng.choices(["OURO", "PRATA", "BRONZE"], [0.20, 0.50, 0.30])[0]
            else:
                tier = rng.choices(["OURO", "PRATA", "BRONZE"], [0.10, 0.30, 0.60])[0]

            serie_base = serie_por_gefin.get(gefin_escolhido, [0.65] * len(meses))
            hist_loja = []
            for idx_m, m_ref in enumerate(ultimos_12_meses):
                sh_base = serie_base[idx_m % len(serie_base)]
                sh_loja = round(clip(sh_base + rng.uniform(-0.05, 0.05), 0.05, 0.98), 4)
                hist_loja.append({"mes_referencia": m_ref, "share_estimado": sh_loja})

            loja["gefin_id"] = gefin_escolhido
            loja["tier_loja"] = tier
            loja["historico_share"] = hist_loja
            lojas_enriquecidas.append(loja)

    print(f" -> {len(lojas_enriquecidas)} lojas únicas carteirizadas por UF e Município!")
    return lojas_enriquecidas

def preparar_lojas(lojas_brutas, gefin_info, rng, args):
    validas, ignoradas, cnpjs_vistos = [], 0, set()
    for loja in lojas_brutas:
        cnpj = loja.get("cnpj")
        if cnpj and cnpj not in cnpjs_vistos and loja.get("gefin_id") in gefin_info:
            cnpjs_vistos.add(cnpj)
            validas.append(loja)
        else:
            ignoradas += 1

    ef_tier, _ = efeitos_por_valor([l.get("tier_loja") for l in validas], args.tier_ordem)
    ef_porte, _ = efeitos_por_valor([l.get("porte") for l in validas], args.porte_ordem)

    print(f" -> Lojas lidas: {len(lojas_brutas)} | Válidas: {len(validas)} | Ignoradas: {ignoradas}")

    ativas = []
    for loja in validas:
        e_tier = ef_tier.get(_norm(loja.get("tier_loja", "")), 0.0)
        e_porte = ef_porte.get(_norm(loja.get("porte", "")), 0.0)
        p_ativa = min(0.95, max(0.02, args.fracao_ativa * (1 + 0.10 * e_tier + 0.05 * e_porte)))
        if rng.random() >= p_ativa:
            continue
        intensidade = min(rng.lognormvariate(0.0, 0.8), 7.0) * (1 + 0.15 * e_tier) * (1 + 0.10 * e_porte)
        ativas.append({
            "cnpj": loja["cnpj"],
            "razao_social": loja.get("razao_social", ""),
            "gefin": loja["gefin_id"],
            "uf": loja.get("endereco_uf") or gefin_info[loja["gefin_id"]]["uf"],
            "e_tier": e_tier,
            "e_porte": e_porte,
            "intens": max(intensidade, 0.02),
            "cresc": rng.gauss(0.0, 0.012),
            "qual": rng.gauss(0.0, 0.02),
        })
    media = sum(l["intens"] for l in ativas) / max(1, len(ativas))
    for loja in ativas:
        loja["intens"] *= args.media_prop_mes / media
    return ativas

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
        inad = round(clip(
            3.4 + 2.5 * (ltv - 0.675) + 0.12 * prazo_idx + (0.15 if not novo else 0.0)
            + AJUSTE_INAD_CATEGORIA[categoria] - 0.12 * loja["e_tier"] - 0.05 * loja["e_porte"]
            + hab["inad"] + rng.gauss(0.0, 0.7),
            0.2, 12.0,
        ), 2)
        dt_form = min(dt_prop + timedelta(days=rng.randint(0, 7), hours=rng.randint(0, 5), minutes=rng.randint(0, 59)), agora)
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
            "valor_bem": valor_bem
        },
        "condicoes_solicitadas": {
            "valor_entrada": entrada,
            "valor_financiado": financiado,
            "prazo_meses": prazo
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
            "inadimplencia_percentual": inad
        },
    }

def gerar_propostas_e_metas(rng, lojas, gefin_info, share_series, meses, agora):
    """
    Motor central de geração sintética.
    Modelo baseado no histórico da loja, introduzindo choques macroeconómicos 
    por UF e sazonalidade
    Gera o facto de 'Metas' e as 'Propostas' já atreladas ao CNPJ da loja.
    """
    choque_nac = [math.exp(rng.gauss(0.0, 0.025)) for _ in meses]
    ufs = sorted({l["uf"] for l in lojas})
    choque_uf = {uf: [math.exp(rng.gauss(0.0, 0.035)) for _ in meses] for uf in ufs}
    habilidade = {gid: {
        "conv": rng.gauss(0.0, 0.02),
        "inad": rng.gauss(0.0, 0.20)
    } for gid in gefin_info}

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
    parser = argparse.ArgumentParser(description="Gerador Sintético Regionalizado BF GeoSmart v2")
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--salvar-local", action="store_true")
    parser.add_argument("--inicio", default=INICIO_PADRAO)
    parser.add_argument("--ate", default=None)
    parser.add_argument("--hoje", default=None)
    parser.add_argument("--fracao-ativa", type=float, default=0.60)
    parser.add_argument("--media-prop-mes", type=float, default=1.0)
    parser.add_argument("--tier-ordem", default=None)
    parser.add_argument("--porte-ordem", default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    args.tier_ordem = args.tier_ordem.split(",") if args.tier_ordem else None
    args.porte_ordem = args.porte_ordem.split(",") if args.porte_ordem else None

    print("1. Inicializando gerador sintético regionalizado...")
    load_dotenv(override=True)
    semente = args.seed if args.seed is not None else int(os.getenv("SEED", str(SEED_PADRAO)))
    agora = (
        datetime.strptime(args.hoje, "%Y-%m-%d").replace(hour=23, minute=59)
        if args.hoje
        else datetime.now(FUSO_BRASIL).replace(tzinfo=None, second=0, microsecond=0)
    )
    ate = args.ate or agora.strftime("%Y-%m")
    meses = lista_meses(args.inicio, ate)
    output_dir = Path(os.getenv("OUTPUT_DIR", OUTPUT_PADRAO))

    print("2. Gerando Colaboradores (SUCOM, GECOM e GEFIN com Lat/Long e UF)...")
    colaboradores = gerar_colaboradores_bf(random.Random(semente))
    info = indexar_gefins(colaboradores, meses, random.Random(semente + 11))
    gefin_ids = sorted(info)
    share_registros, share_series = gerar_historico_marketing_share(
        random.Random(semente + 21), gefin_ids, meses
    )

    print("3. Carregando lojas da camada Silver e vinculando por UF e Município...")
    lojas_enriquecidas = carregar_e_vincular_lojas_silver(
        colaboradores, share_series, meses, random.Random(semente + 25)
    )
    lojas_ativas = preparar_lojas(
        lojas_enriquecidas, info, random.Random(semente + 31), args
    )

    print(f"4. Gerando Propostas e Metas ({meses[0]} até {meses[-1]})...")
    propostas, metas = gerar_propostas_e_metas(
        random.Random(semente + 41), lojas_ativas, info, share_series, meses, agora
    )

    arquivos_silver = {
        "dados_sinteticos/lojas_enriquecidas.json": lojas_enriquecidas,
        "dados_sinteticos/colaboradores.json": colaboradores,
        "dados_sinteticos/propostas.json": propostas,
        "dados_sinteticos/historico_share.json": share_registros,
        "dados_sinteticos/metas_loja.json": metas,
    }

    if args.local_only or args.salvar_local:
        for caminho_blob, dados in arquivos_silver.items():
            caminho_local = output_dir / Path(caminho_blob).name
            salvar_json_local(caminho_local, dados)

    if args.local_only:
        return

    print("\n5. Enviando dados para a camada Silver no Azure Data Lake...")
    for caminho_blob, dados in arquivos_silver.items():
        datalake.upload_json("silver", caminho_blob, dados)
        print(f" -> silver/{caminho_blob} enviado ({len(dados)} registros)")

    print("\nPipeline 03 concluída com sucesso!")

if __name__ == "__main__":
    main()