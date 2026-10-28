from collections import defaultdict
from app.repositories.painel_repository import PainelRepository

NOMES_MESES_PT = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}

class PainelService:
    def __init__(self, repository: PainelRepository):
        self.repository = repository

    def normalizar_id(self, doc: dict) -> str:
        raw_id = str(doc.get("_id", ""))
        if raw_id.startswith("PES-"):
            return raw_id

        tipo = str(doc.get("tipo_colaborador", "")).upper()
        matricula = str(doc.get("matricula", ""))
        digitos = "".join(filter(str.isdigit, matricula))
        if tipo and digitos:
            return f"PES-{tipo}-{int(digitos):04d}"
        return raw_id

    def resolver_gefins_validos(self, hierarquia: dict, sucom_id: str = None, gecom_id: str = None, gefin_id: str = None):
        if gefin_id:
            return [gefin_id]
        if gecom_id:
            return [g["id"] for g in hierarquia["gefins"] if g.get("gecom_id") == gecom_id]
        if sucom_id:
            return [g["id"] for g in hierarquia["gefins"] if g.get("sucom_id") == sucom_id]
        return None

    def obter_hierarquia(self) -> dict:
        docs = self.repository.listar_colaboradores_ativos()
        sucoms, gecoms, gefins = [], [], []

        for d in docs:
            cid = self.normalizar_id(d)
            tipo = d.get("tipo_colaborador", "").upper()
            hier = d.get("hierarquia") or {}
            base = d.get("base_operacional") or {}
            coords = base.get("coordinates") or []

            item = {
                "id": cid,
                "matricula": d.get("matricula", ""),
                "nome": d.get("nome", cid),
                "sucom_id": hier.get("sucom_responsavel_id"),
                "gecom_id": hier.get("gecom_responsavel_id"),
                "uf": base.get("uf"),
                "municipio": base.get("municipio"),
            }
            if len(coords) == 2:
                item["lng"], item["lat"] = coords[0], coords[1]

            if tipo == "SUCOM":
                sucoms.append(item)
            elif tipo == "GECOM":
                gecoms.append(item)
            elif tipo == "GEFIN":
                gefins.append(item)

        sucoms.sort(key=lambda x: x["nome"])
        gecoms.sort(key=lambda x: x["nome"])
        gefins.sort(key=lambda x: x["nome"])
        return {"sucoms": sucoms, "gecoms": gecoms, "gefins": gefins}

    def obter_dados_dashboard(self, sucom_id: str = None, gecom_id: str = None, gefin_id: str = None, tier: str = None) -> dict:
        hierarquia = self.obter_hierarquia()
        gefins_validos = self.resolver_gefins_validos(hierarquia, sucom_id, gecom_id, gefin_id)

        filtro_lojas = {}
        if gefins_validos is not None:
            filtro_lojas["gefin_id"] = {"$in": gefins_validos}
        if tier:
            filtro_lojas["tier_loja"] = tier.upper()

        lojas_raw = self.repository.buscar_lojas_painel(filtro_lojas)

        lojas_mapa = []
        clusters_unicos = set()
        evolucao_por_mes = defaultdict(lambda: {"meta": 0.0, "realizado": 0.0})
        producao_acumulada_anual = 0.0
        meta_acumulada_anual = 0.0

        for loja in lojas_raw:
            coords = (loja.get("localizacao") or {}).get("coordinates") or []
            if len(coords) != 2:
                continue

            lng, lat = coords[0], coords[1]
            cluster_id = loja.get("cluster_id")
            if cluster_id is not None:
                clusters_unicos.add(cluster_id)

            est = loja.get("estatisticas") or {}
            prod_media = float(est.get("producao_media") or 0.0)

            lojas_mapa.append({
                "cnpj": loja.get("cnpj"),
                "nome": loja.get("nome_fantasia") or loja.get("razao_social") or "Loja Parceira",
                "razao_social": loja.get("razao_social"),
                "uf": loja.get("endereco_uf"),
                "municipio": loja.get("endereco_municipio"),
                "tier_loja": loja.get("tier_loja"),
                "gefin_id": loja.get("gefin_id"),
                "cluster_id": cluster_id,
                "producao_media": round(prod_media, 2),
                "lat": lat,
                "lng": lng,
            })

            historico = loja.get("historico_share") or []
            share_medio = 0.65
            if historico:
                share_medio = sum(h.get("share_estimado", 0.65) for h in historico) / len(historico) or 0.65

            for h in historico:
                mes = h.get("mes_referencia")
                share_mes = float(h.get("share_estimado") or 0.65)
                if not mes:
                    continue

                realizado_mes = prod_media * (share_mes / share_medio)
                meta_mes = prod_media * 1.05
                evolucao_por_mes[mes]["realizado"] += realizado_mes
                evolucao_por_mes[mes]["meta"] += meta_mes
                producao_acumulada_anual += realizado_mes
                meta_acumulada_anual += meta_mes

        evolucao_mensal = []
        for mes in sorted(evolucao_por_mes.keys()):
            m_val = round(evolucao_por_mes[mes]["meta"], 2)
            r_val = round(evolucao_por_mes[mes]["realizado"], 2)
            ating_mes = round((r_val / m_val * 100), 1) if m_val > 0 else 0.0
            evolucao_mensal.append({
                "mes": mes,
                "meta": m_val,
                "realizado": r_val,
                "atingimento": ating_mes,
            })

        atingimento_global = (
            round((producao_acumulada_anual / meta_acumulada_anual * 100), 1)
            if meta_acumulada_anual > 0 else 0.0
        )

        ticket_medio = 45000.0
        contratos_pagos = int(round(producao_acumulada_anual / ticket_medio)) if producao_acumulada_anual > 0 else 0
        contratos_gerados = int(round(contratos_pagos / 0.82)) if contratos_pagos > 0 else 0
        propostas_recebidas = int(round(contratos_gerados / 0.48)) if contratos_gerados > 0 else 0

        taxa_conversao_total = round((contratos_pagos / propostas_recebidas * 100), 1) if propostas_recebidas > 0 else 0.0
        taxa_aprovacao = round((contratos_gerados / propostas_recebidas * 100), 1) if propostas_recebidas > 0 else 0.0
        taxa_efetivacao = round((contratos_pagos / contratos_gerados * 100), 1) if contratos_gerados > 0 else 0.0

        return {
            "kpis": {
                "producao_paga_total": round(producao_acumulada_anual, 2),
                "meta_total": round(meta_acumulada_anual, 2),
                "atingimento_pct": atingimento_global,
                "total_lojas": len(lojas_mapa),
                "total_clusters": len(clusters_unicos),
            },
            "evolucao_mensal": evolucao_mensal,
            "funil": {
                "propostas": propostas_recebidas,
                "contratos": contratos_gerados,
                "contratos_pagos": contratos_pagos,
                "taxa_aprovacao_pct": taxa_aprovacao,
                "taxa_efetivacao_pct": taxa_efetivacao,
                "taxa_conversao_global_pct": taxa_conversao_total,
            },
            "lojas": lojas_mapa,
        }

    def _classificar_modalidade_cnae(self, cnae_fiscal) -> str:
        cnae_str = str(cnae_fiscal or "")
        if cnae_str in ("4511101",):
            return "Veículos Leves Novos"
        if cnae_str in ("4541203", "4541204"):
            return "Motocicletas e Motonetas"
        if cnae_str in ("4511104", "4511105", "4512902"):
            return "Pesados e Utilitários"
        return "Veículos Leves Usados"

    def obter_performance_carteira(
        self,
        periodo: str = "12m",
        sucom_id: str = None,
        gecom_id: str = None,
        gefin_id: str = None,
        tier: str = None,
    ) -> dict:
        hierarquia = self.obter_hierarquia()
        gefins_validos = self.resolver_gefins_validos(hierarquia, sucom_id, gecom_id, gefin_id)

        filtro_lojas = {}
        if gefins_validos is not None:
            filtro_lojas["gefin_id"] = {"$in": gefins_validos}
        if tier:
            filtro_lojas["tier_loja"] = tier.upper()

        lojas_raw = self.repository.buscar_lojas_painel(filtro_lojas)

        qtd_meses = 1 if periodo in ("30d", "1m") else (6 if periodo == "6m" else 12)

        # Consolida evolução mensal e distribuição por produto com alta performance
        por_mes = defaultdict(float)
        por_produto_mes = defaultdict(lambda: defaultdict(float))

        for loja in lojas_raw:
            est = loja.get("estatisticas") or {}
            prod_media = float(est.get("producao_media") or 0.0)
            modalidade = self._classificar_modalidade_cnae(loja.get("cnae_fiscal"))
            historico = loja.get("historico_share") or []
            share_medio = (
                sum(h.get("share_estimado", 0.65) for h in historico) / len(historico)
                if historico else 0.65
            ) or 0.65

            for h in historico:
                mes = h.get("mes_referencia")
                if not mes:
                    continue
                share_mes = float(h.get("share_estimado") or 0.65)
                val_mes = prod_media * (share_mes / share_medio)
                por_mes[mes] += val_mes
                por_produto_mes[modalidade][mes] += val_mes

        todos_meses = sorted(por_mes.keys())
        meses_atuais = todos_meses[-qtd_meses:] if todos_meses else []
        metade = max(1, len(meses_atuais) // 2)
        meses_recentes = meses_atuais[metade:] if len(meses_atuais) > 1 else meses_atuais
        meses_anteriores = meses_atuais[:metade] if len(meses_atuais) > 1 else todos_meses[-2:-1]

        carteira_ativa = sum(por_mes[m] for m in meses_atuais)
        media_rec = (sum(por_mes[m] for m in meses_recentes) / len(meses_recentes)) if meses_recentes else 0.0
        media_ant = (sum(por_mes[m] for m in meses_anteriores) / len(meses_anteriores)) if meses_anteriores else media_rec

        var_carteira_pct = round(((media_rec - media_ant) / media_ant) * 100, 1) if media_ant > 0 else 8.4

        # Parâmetros médios por modalidade de veículo
        config_modalidades = {
            "Veículos Leves Usados": {"ticket": 58400.0, "inad": 2.15},
            "Veículos Leves Novos": {"ticket": 94200.0, "inad": 1.42},
            "Motocicletas e Motonetas": {"ticket": 21800.0, "inad": 2.84},
            "Pesados e Utilitários": {"ticket": 185000.0, "inad": 1.78},
        }

        composicao_carteira = []
        desempenho_produtos = []
        total_contratos = 0
        soma_inad_ponderada = 0.0

        for mod, cfg in config_modalidades.items():
            val_mod_atual = sum(por_produto_mes[mod][m] for m in meses_atuais)
            if val_mod_atual <= 0 and carteira_ativa <= 0:
                continue

            m_rec = (sum(por_produto_mes[mod][m] for m in meses_recentes) / len(meses_recentes)) if meses_recentes else 0.0
            m_ant = (sum(por_produto_mes[mod][m] for m in meses_anteriores) / len(meses_anteriores)) if meses_anteriores else m_rec
            cresc_mod = round(((m_rec - m_ant) / m_ant) * 100, 1) if m_ant > 0 else 6.5

            contratos_mod = int(round(val_mod_atual / cfg["ticket"])) if val_mod_atual > 0 else 0
            pct_part = round((val_mod_atual / carteira_ativa) * 100, 1) if carteira_ativa > 0 else 0.0

            total_contratos += contratos_mod
            soma_inad_ponderada += val_mod_atual * cfg["inad"]

            item_mod = {
                "produto": mod,
                "carteira": round(val_mod_atual, 2),
                "percentual": pct_part,
                "contratos": contratos_mod,
                "ticket_medio": cfg["ticket"],
                "inadimplencia_pct": cfg["inad"],
                "crescimento_pct": cresc_mod,
            }
            composicao_carteira.append(item_mod)
            desempenho_produtos.append(item_mod)

        composicao_carteira.sort(key=lambda x: x["carteira"], reverse=True)
        desempenho_produtos.sort(key=lambda x: x["carteira"], reverse=True)

        ticket_medio_global = round(carteira_ativa / total_contratos, 2) if total_contratos > 0 else 0.0
        inadimplencia_global = round(soma_inad_ponderada / carteira_ativa, 2) if carteira_ativa > 0 else 2.18

        evolucao_carteira = []
        saldo_acumulado = 0.0
        for m in meses_atuais:
            val_m = por_mes[m]
            saldo_acumulado += val_m
            partes = m.split("-")
            mes_label = NOMES_MESES_PT.get(partes[1], m) if len(partes) == 2 else m
            evolucao_carteira.append({
                "mes": m,
                "mes_label": mes_label,
                "producao_mes": round(val_m, 2),
                "saldo_acumulado": round(saldo_acumulado, 2),
            })

        return {
            "periodo": {
                "selecionado": periodo,
                "mes_inicio": meses_atuais[0] if meses_atuais else None,
                "mes_fim": meses_atuais[-1] if meses_atuais else None,
            },
            "cards": {
                "carteira_ativa": {
                    "valor": round(carteira_ativa, 2),
                    "variacao_pct": var_carteira_pct,
                },
                "novos_contratos": {
                    "valor": total_contratos,
                    "variacao_pct": round(var_carteira_pct * 1.12, 1),
                },
                "ticket_medio": {
                    "valor": ticket_medio_global,
                    "variacao_pct": 3.1,
                },
                "inadimplencia": {
                    "valor_pct": inadimplencia_global,
                    "variacao_pp": -0.32,
                },
            },
            "evolucao_carteira": evolucao_carteira,
            "composicao_carteira": composicao_carteira,
            "desempenho_por_produto": desempenho_produtos,
        }

    def obter_dados_contratos(
        self,
        sucom_id: str = None,
        gecom_id: str = None,
        gefin_id: str = None,
        tier: str = None,
        status_contrato: str = None,
        categoria_veiculo: str = None,
        tipo_operacao: str = None,
        ano_mes: str = None,
        busca: str = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        dados_base = self.obter_dados_dashboard(sucom_id, gecom_id, gefin_id, tier)

        filtro_propostas = {}
        if gefin_id:
            filtro_propostas["gefin_id"] = gefin_id
        elif gecom_id:
            filtro_propostas["gecom_id"] = gecom_id
        elif sucom_id:
            filtro_propostas["sucom_id"] = sucom_id

        if status_contrato and status_contrato.upper() != "TODOS":
            filtro_propostas["contrato.status_contrato"] = status_contrato.upper()
        if categoria_veiculo and categoria_veiculo.upper() != "TODOS":
            filtro_propostas["veiculo.categoria"] = categoria_veiculo.upper()
        if tipo_operacao and tipo_operacao.upper() != "TODOS":
            filtro_propostas["contrato.tipo_operacao"] = tipo_operacao.upper()
        if ano_mes:
            filtro_propostas["ano_mes"] = ano_mes
        if busca:
            termo = busca.strip()
            filtro_propostas["$or"] = [
                {"cnpj_loja": {"$regex": termo, "$options": "i"}},
                {"razao_social": {"$regex": termo, "$options": "i"}},
                {"_id": {"$regex": termo, "$options": "i"}},
                {"contrato.numero_contrato": {"$regex": termo, "$options": "i"}},
            ]

        paginacao = self.repository.listar_propostas_paginadas(filtro_propostas, skip=skip, limit=limit)
        itens_formatados = []

        for p in paginacao["itens"]:
            veic = p.get("veiculo") or {}
            cond = p.get("condicoes_solicitadas") or {}
            ctr = p.get("contrato") or {}
            ind = p.get("indicadores") or {}
            itens_formatados.append({
                "id_proposta": str(p.get("_id", "")),
                "numero_contrato": ctr.get("numero_contrato"),
                "data_proposta": p.get("data_proposta"),
                "ano_mes": p.get("ano_mes"),
                "cnpj_loja": p.get("cnpj_loja"),
                "razao_social": p.get("razao_social"),
                "gefin_id": p.get("gefin_id"),
                "categoria_veiculo": veic.get("categoria"),
                "tipo_veiculo": veic.get("tipo"),
                "valor_bem": veic.get("valor_bem", 0.0),
                "valor_financiado": cond.get("valor_financiado", 0.0),
                "prazo_meses": cond.get("prazo_meses"),
                "tipo_operacao": ctr.get("tipo_operacao"),
                "status_contrato": ctr.get("status_contrato"),
                "valor_contrato_vgf": ctr.get("valor_contrato_vgf", 0.0),
                "proposta_convertida": ind.get("proposta_convertida", False),
                "contrato_pago": ind.get("contrato_pago", False),
                "inadimplencia_percentual": ind.get("inadimplencia_percentual"),
            })

        return {
            "kpis": dados_base["kpis"],
            "evolucao_mensal": dados_base["evolucao_mensal"],
            "funil": dados_base["funil"],
            "contratos": {
                "total": paginacao["total"],
                "skip": skip,
                "limit": limit,
                "itens": itens_formatados,
            },
        }