import os
import subprocess
from fastapi import APIRouter, Query, status, HTTPException
from pymongo import MongoClient
from dotenv import load_dotenv

from app.models.loja_model import LojaCreate, LojaUpdate
from app.repositories.loja_repository import LojaRepository
from app.services.loja_service import LojaService

load_dotenv(override=True)

# Conexão Global do MongoDB
uri_mongo = os.getenv("COSMOS_MONGO_URI")
db_name = os.getenv("COSMOS_DB_NAME", "bf_geosmart")

if not uri_mongo:
    raise ValueError("A variável COSMOS_MONGO_URI não foi encontrada no .env")

client = MongoClient(uri_mongo)
lojas_col = client[db_name]['lojas']

# Instanciação das camadas
repository = LojaRepository(lojas_col)
service = LojaService(repository)

router = APIRouter(prefix="/lojas", tags=["Lojas"])

@router.post("/", status_code=status.HTTP_201_CREATED, summary="Cadastrar nova loja")
async def create_loja(loja: LojaCreate):
    return service.registrar_loja(loja)

@router.get("/", summary="Listar lojas (com filtros e paginação)")
async def get_lojas(
    uf: str = Query(None, description="Filtrar por UF"),
    tier: str = Query(None, description="Filtrar por Tier (OURO, PRATA, BRONZE)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    return service.consultar_lojas(uf, tier, skip, limit)

@router.get("/{cnpj}", summary="Buscar detalhes de uma loja")
async def get_loja_by_cnpj(cnpj: str):
    return service.buscar_loja_unica(cnpj)

@router.patch("/{cnpj}", summary="Atualizar dados cadastrais")
async def update_loja(cnpj: str, loja_update: LojaUpdate):
    return service.modificar_loja(cnpj, loja_update)

@router.delete("/{cnpj}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir loja")
async def delete_loja(cnpj: str):
    service.remover_loja(cnpj)
    return None