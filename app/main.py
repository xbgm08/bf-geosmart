from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.loja_router import router as loja_router
from app.routers.painel_router import router as painel_router

app = FastAPI(
    title="API GeoSmart - Back-end",
    description="API arquitetada em camadas (Router-Service-Repository) para integração com Cosmos DB.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(loja_router)
app.include_router(painel_router)

@app.get("/", tags=["Status"])
def root():
    return {"status": "online", "service": "BF GeoSmart API"}