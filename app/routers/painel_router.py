import os
from typing import Optional
from fastapi import APIRouter, Query
from pymongo import MongoClient
from dotenv import load_dotenv

from app.repositories.painel_repository import PainelRepository
from app.services.painel_service import PainelService

load_dotenv(override=True)

uri_mongo = os.getenv("COSMOS_MONGO_URI")
db_name = os.getenv("COSMOS_DB_NAME", "bf_geosmart")

client = MongoClient(uri_mongo)
db = client[db_name]

repository = PainelRepository(db)
service = PainelService(repository)

router = APIRouter(prefix="/painel", tags=["Painel Analítico"])

@router.get("/hierarquia", summary="Retorna a árvore SUCOM -> GECOM -> GEFIN ativa")
async def get_hierarquia():
    return service.obter_hierarquia()

@router.get("/dados", summary="Retorna lojas geolocalizadas, KPIs, evolução mensal e funil comercial (Visão Geral)")
async def get_dados_painel(
    sucom_id: Optional[str] = Query(None, description="ID do SUCOM (ex: PES-SUCOM-0001)"),
    gecom_id: Optional[str] = Query(None, description="ID do GECOM (ex: PES-GECOM-0013)"),
    gefin_id: Optional[str] = Query(None, description="ID do GEFIN (ex: PES-GEFIN-0087)"),
    tier: Optional[str] = Query(None, description="Filtrar por Tier (OURO, PRATA, BRONZE)"),
):
    return service.obter_dados_dashboard(sucom_id, gecom_id, gefin_id, tier)

@router.get("/performance", summary="Retorna os indicadores executivos da Aba Performance da Carteira")
async def get_performance_carteira(
    periodo: str = Query("12m", description="Período: 30d, 6m ou 12m"),
    sucom_id: Optional[str] = Query(None, description="ID do SUCOM"),
    gecom_id: Optional[str] = Query(None, description="ID do GECOM"),
    gefin_id: Optional[str] = Query(None, description="ID do GEFIN"),
    tier: Optional[str] = Query(None, description="Filtrar por Tier (OURO, PRATA, BRONZE)"),
):
    return service.obter_performance_carteira(periodo, sucom_id, gecom_id, gefin_id, tier)

@router.get("/contratos", summary="Retorna Funil, Meta vs. Realizado e listagem paginada para a Aba Contratos")
async def get_contratos_painel(
    sucom_id: Optional[str] = Query(None, description="ID do SUCOM"),
    gecom_id: Optional[str] = Query(None, description="ID do GECOM"),
    gefin_id: Optional[str] = Query(None, description="ID do GEFIN"),
    tier: Optional[str] = Query(None, description="Filtrar por Tier"),
    status_contrato: Optional[str] = Query(None, description="PAGO, ATIVO ou NAO_CONVERTIDA"),
    categoria_veiculo: Optional[str] = Query(None, description="LEVE, MOTOS ou PESADOS"),
    tipo_operacao: Optional[str] = Query(None, description="CDC ou LEASING"),
    ano_mes: Optional[str] = Query(None, description="Filtro por mês (ex: 2026-10)"),
    busca: Optional[str] = Query(None, description="Busca por CNPJ, Razão Social ou Nº do Contrato"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return service.obter_dados_contratos(
        sucom_id=sucom_id,
        gecom_id=gecom_id,
        gefin_id=gefin_id,
        tier=tier,
        status_contrato=status_contrato,
        categoria_veiculo=categoria_veiculo,
        tipo_operacao=tipo_operacao,
        ano_mes=ano_mes,
        busca=busca,
        skip=skip,
        limit=limit,
    )