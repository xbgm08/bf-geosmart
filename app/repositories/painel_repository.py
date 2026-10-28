from pymongo.database import Database

class PainelRepository:
    def __init__(self, db: Database):
        self.db = db
        nomes_col = db.list_collection_names()

        self.lojas_col = db["lojas"]
        self.colaboradores_col = (
            db["colaboradores"] if "colaboradores" in nomes_col else None
        )
        self.kpis_loja_col = (
            db["kpis_loja_mes"] if "kpis_loja_mes" in nomes_col else None
        )
        self.kpis_gefin_col = (
            db["kpis_gefin_mes"] if "kpis_gefin_mes" in nomes_col else None
        )
        self.propostas_col = db["propostas"] if "propostas" in nomes_col else None

    def listar_colaboradores_ativos(self) -> list:
        if self.colaboradores_col is None:
            return []
        return list(self.colaboradores_col.find({"ativo": True}))

    def buscar_lojas_painel(self, filtro_lojas: dict) -> list:
        projecao = {
            "_id": 0,
            "cnpj": 1,
            "razao_social": 1,
            "nome_fantasia": 1,
            "cnae_fiscal": 1,
            "cnae_fiscal_descricao": 1,
            "endereco_uf": 1,
            "endereco_municipio": 1,
            "gefin_id": 1,
            "tier_loja": 1,
            "localizacao": 1,
            "historico_share": 1,
            "estatisticas": 1,
            "cluster_id": 1,
        }
        return list(self.lojas_col.find(filtro_lojas, projecao))

    def buscar_kpis_mensais(self, cnpjs: list) -> list:
        if self.kpis_loja_col is None:
            return []
        query = {"cnpj_loja": {"$in": cnpjs}} if cnpjs else {}
        return list(self.kpis_loja_col.find(query, {"_id": 0}))

    def buscar_resumo_propostas(self, filtro_hierarquia: dict) -> list:
        if self.propostas_col is None:
            return []
        pipeline = [
            {"$match": filtro_hierarquia},
            {"$group": {"_id": "$contrato.status_contrato", "total": {"$sum": 1}}},
        ]
        return list(self.propostas_col.aggregate(pipeline))

    def listar_propostas_paginadas(
        self, filtro: dict, skip: int = 0, limit: int = 20
    ) -> dict:
        if self.propostas_col is None:
            return {"total": 0, "itens": []}

        total = self.propostas_col.count_documents(filtro)
        projecao = {
            "_id": 1,
            "data_proposta": 1,
            "ano_mes": 1,
            "cnpj_loja": 1,
            "razao_social": 1,
            "gefin_id": 1,
            "gecom_id": 1,
            "sucom_id": 1,
            "veiculo": 1,
            "condicoes_solicitadas": 1,
            "contrato": 1,
            "indicadores": 1,
        }
        cursor = (
            self.propostas_col.find(filtro, projecao)
            .sort("data_proposta", -1)
            .skip(skip)
            .limit(limit)
        )
        return {"total": total, "itens": list(cursor)}