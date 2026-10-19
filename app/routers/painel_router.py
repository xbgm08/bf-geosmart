import os
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

@router.get("/dados", summary="Retorna lojas geolocalizadas, KPIs, evolução mensal e funil comercial")
async def get_dados_painel(
    sucom_id: str = Query(None, description="ID da SUCOM (ex: PES-SUCOM-0001)"),
    gecom_id: str = Query(None, description="ID do GECOM (ex: PES-GECOM-0013)"),
    gefin_id: str = Query(None, description="ID do GEFIN (ex: PES-GEFIN-0087)"),
    tier: str = Query(None, description="Filtrar por Tier (OURO, PRATA, BRONZE)")
):
    return service.obter_dados_dashboard(sucom_id, gecom_id, gefin_id, tier)