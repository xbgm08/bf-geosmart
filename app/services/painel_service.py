from app.repositories.painel_repository import PainelRepository
from collections import defaultdict

class PainelService:
    def __init__(self, repository: PainelRepository):
        self.repository = repository

    def _normalizar_id(self, doc: dict) -> str:
        raw_id = str(doc.get("_id", ""))
        if raw_id.startswith("PES-"):
            return raw_id
        
        tipo = str(doc.get("tipo_colaborador", "")).upper()
        matricula = str(doc.get("matricula", ""))
        digitos = "".join(filter(str.isdigit, matricula))
        if tipo and digitos:
            return f"PES-{tipo}-{int(digitos):04d}"
        return raw_id

    def obter_hierarquia(self) -> dict:
        docs = self.repository.listar_colaboradores_ativos()
        sucoms, gecoms, gefins = [], [], []

        for d in docs:
            cid = self._normalizar_id(d)
            tipo = d.get("tipo_colaborador", "").upper()
            hier = d.get("hierarquia") or {}

            item = {
                "id": cid,
                "matricula": d.get("matricula", ""),
                "nome": d.get("nome", cid),
                "sucom_id": hier.get("sucom_responsavel_id"),
                "gecom_id": hier.get("gecom_responsavel_id"),
            }

            if tipo == "SUCOM":
                sucoms.append(item)
            elif tipo == "GECOM":
                gecoms.append(item)
            elif tipo == "GEFIN":
                base = d.get("base_operacional") or {}
                coords = base.get("coordinates") or []
                if len(coords) == 2:
                    item["lng"], item["lat"] = coords[0], coords[1]
                    item["uf"] = base.get("uf")
                    item["municipio"] = base.get("municipio")
                gefins.append(item)

        sucoms.sort(key=lambda x: x["nome"])
        gecoms.sort(key=lambda x: x["nome"])
        gefins.sort(key=lambda x: x["nome"])
        return {"sucoms": sucoms, "gecoms": gecoms, "gefins": gefins}

    def obter_dados_dashboard(
        self, sucom_id: str = None, gecom_id: str = None, gefin_id: str = None, tier: str = None
    ) -> dict:
        hierarquia = self.obter_hierarquia()
        gefins_validos = None

        if gefin_id:
            gefins_validos = [gefin_id]
        elif gecom_id:
            gefins_validos = [g["id"] for g in hierarquia["gefins"] if g.get("gecom_id") == gecom_id]
        elif sucom_id:
            gefins_validos = [g["id"] for g in hierarquia["gefins"] if g.get("sucom_id") == sucom_id]

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
                "lng": lng
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
                "atingimento": ating_mes
            })

        atingimento_global = round(
            (producao_acumulada_anual / meta_acumulada_anual * 100), 1
        ) if meta_acumulada_anual > 0 else 0.0

        ticket_medio = 45000.0
        contratos_pagos = int(round(producao_acumulada_anual / ticket_medio)) if producao_acumulada_anual > 0 else 0
        contratos_gerados = int(round(contratos_pagos / 0.82)) if contratos_pagos > 0 else 0
        propostas_recebidas = int(round(contratos_gerados / 0.48)) if contratos_gerados > 0 else 0

        taxa_conversao_total = round(
            (contratos_pagos / propostas_recebidas * 100), 1
        ) if propostas_recebidas > 0 else 0.0
        taxa_aprovacao = round(
            (contratos_gerados / propostas_recebidas * 100), 1
        ) if propostas_recebidas > 0 else 0.0
        taxa_efetivacao = round(
            (contratos_pagos / contratos_gerados * 100), 1
        ) if contratos_gerados > 0 else 0.0

        return {
            "kpis": {
                "producao_paga_total": round(producao_acumulada_anual, 2),
                "meta_total": round(meta_acumulada_anual, 2),
                "atingimento_pct": atingimento_global,
                "total_lojas": len(lojas_mapa),
                "total_clusters": len(clusters_unicos)
            },
            "evolucao_mensal": evolucao_mensal,
            "funil": {
                "propostas": propostas_recebidas,
                "contratos": contratos_gerados,
                "contratos_pagos": contratos_pagos,
                "taxa_aprovacao_pct": taxa_aprovacao,
                "taxa_efetivacao_pct": taxa_efetivacao,
                "taxa_conversao_global_pct": taxa_conversao_total
            },
            "lojas": lojas_mapa
        }