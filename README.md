# BF GeoSmart

O **BF GeoSmart** é uma plataforma de Engenharia de Dados, Machine Learning e
Inteligência Geográfica desenvolvida para o **Bradesco Financiamentos (BF)**.
A solução apoia a gestão territorial e a redistribuição estratégica de lojas
parceiras do setor automotivo na hierarquia comercial do banco:
**SUCOM**, **GECOM**, **GEFIN** e **Lojas**.

O projeto integra pipelines de dados em arquitetura **Medallion (Bronze,
Silver e Gold)**, armazenamento no **Azure Blob Storage**, persistência no
**Azure Cosmos DB for MongoDB**, uma API REST em **FastAPI** e um dashboard
analítico em **React + Vite**.

> Projeto Integrador IV — Big Data para Negócios
> FATEC Ipiranga

## Funcionalidades atuais

- Ingestão e saneamento de empresas do setor automotivo.
- Geração da hierarquia comercial e de dados sintéticos de propostas, metas e
  market share.
- Geocodificação de lojas com coordenadas GeoJSON.
- Cálculo de KPIs mensais por loja e GEFIN.
- Clusterização territorial por UF.
- Classificação de estratégias comerciais.
- Recomendação dos GEFINs mais adequados para cada loja.
- Dashboard com filtros hierárquicos, indicadores, evolução mensal, funil
  comercial e mapa de lojas.
- CRUD de lojas com filtros, busca e paginação.
- Consultas analíticas de visão geral, performance e contratos.

## Arquitetura e fluxo de dados

```text
API Minha Receita
        |
        v
Bronze -> Silver -> Gold -> Azure Blob Storage
                              |
                              v
                    Azure Cosmos DB (MongoDB API)
                              |
                              v
                    FastAPI -> Dashboard React
```

### Pipelines

Os scripts devem ser executados na ordem indicada, a partir da raiz do
projeto:

1. **`01_bronze_ingestao_lojas.py`** — consulta a API pública Minha Receita,
   filtra CNAEs do setor automotivo, remove duplicidades por CNPJ e grava a
   camada Bronze.
2. **`02_silver_saneamento_lojas.py`** — mantém empresas ativas, exclui MEIs
   e padroniza os dados cadastrais e endereços.
3. **`03_silver_ingestão_dados_sintéticos.py`** — gera a hierarquia
   SUCOM/GECOM/GEFIN, a carteirização das lojas e séries históricas de
   propostas, metas e market share.
4. **`04_gold_integracao_camadas.py`** — consolida os arquivos Gold e
   carrega lojas, colaboradores, metas e propostas no Cosmos DB em lotes,
   tratando o limite de throughput `16500`.
5. **`05_gold_geocodificacao_lojas.py`** — geocodifica os endereços com
   Nominatim/OpenStreetMap, usando cache e fallbacks, e grava pontos GeoJSON.
6. **`06_gold_kpis_analytics.py`** — calcula KPIs de negócio com Pandas e
   NumPy e atualiza os indicadores por loja e por GEFIN.
7. **`07_gold_clusterizacao_territorios.py`** — aplica clusterização espacial
   com K-Means para organizar territórios de forma equilibrada.
8. **`08_gold_classificacao_estrategias.py`** — classifica a estratégia
   comercial de cada loja com base no histórico de market share.
9. **`09_gold_recomendacao_gefin.py`** — recomenda até três GEFINs por loja,
   combinando proximidade regional, tempo de deslocamento e carga de trabalho.

Os scripts 5 e 9 dependem de serviços externos de geocodificação e roteamento.
O script 3 aceita `--seed` e `OUTPUT_DIR` para controlar a reprodutibilidade e
o destino dos arquivos gerados.

## Tecnologias

### Dados e backend

- Python 3
- Pandas, NumPy e Scikit-learn
- Requests, Geopy e Tqdm
- FastAPI, Uvicorn e Pydantic
- PyMongo
- Azure Blob Storage
- Azure Cosmos DB for MongoDB

### Frontend

- React 19
- Vite
- Tailwind CSS
- React Leaflet e Leaflet
- Recharts
- Axios

## Pré-requisitos

- Python 3.10 ou superior.
- Node.js e npm.
- Uma conta/configuração do Azure Blob Storage.
- Uma instância do Azure Cosmos DB com a API para MongoDB.
- Acesso à internet para a API Minha Receita, Nominatim/OpenStreetMap e OSRM.

## Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
COSMOS_MONGO_URI="mongodb://..."
COSMOS_DB_NAME="bf_geosmart"
```

Para ajustar a geração e a classificação, também podem ser definidos:

```env
SEED=42
OUTPUT_DIR=dados
COSMOS_LOJAS_COLLECTION=lojas
SHARE_BAIXO=20
SHARE_ALTO=50
DESVIO_MAX_ESTAVEL=8
QUEDA_MINIMA_SHARE=10
```

Não versionar o arquivo `.env` nem suas credenciais.

## Instalação

### Backend e pipelines

Na raiz do repositório:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Frontend

```powershell
cd frontend
npm install
```

## Execução

### 1. Executar as pipelines

Com o ambiente Python ativado, execute:

```powershell
python -m pipelines.01_bronze_ingestao_lojas.py
python -m pipelines.02_silver_saneamento_lojas.py
python -m pipelines.03_silver_ingestão_dados_sintéticos.py
python -m pipelines.04_gold_integracao_camadas.py
python -m pipelines.05_gold_geocodificacao_lojas.py
python -m pipelines.06_gold_kpis_analytics.py
python -m pipelines.07_gold_clusterizacao_territorios.py
python -m pipelines.08_gold_classificacao_estrategias.py
python -m pipelines.09_gold_recomendacao_gefin.py
```

### 2. Iniciar a API

Em um terminal, na raiz do projeto:

```powershell
uvicorn app.main:app --reload
```

A API ficará disponível em `http://localhost:8000`. A documentação interativa
está em:

- Swagger UI: `http://localhost:8000/docs`

#### Principais endpoints

| Método | Endpoint | Finalidade |
|---|---|---|
| GET | `/` | Verificar o status da API |
| GET | `/painel/hierarquia` | Consultar a árvore SUCOM → GECOM → GEFIN |
| GET | `/painel/dados` | Consultar KPIs, evolução, funil e lojas geolocalizadas |
| GET | `/painel/performance` | Consultar indicadores executivos da carteira |
| GET | `/painel/contratos` | Consultar funil, metas e contratos paginados |
| POST | `/lojas/` | Cadastrar uma loja |
| GET | `/lojas/` | Listar lojas com filtros, busca e paginação |
| GET | `/lojas/{cnpj}` | Consultar uma loja pelo CNPJ |
| PATCH | `/lojas/{cnpj}` | Atualizar dados cadastrais |
| DELETE | `/lojas/{cnpj}` | Excluir uma loja |

Os endpoints do painel aceitam filtros por `sucom_id`, `gecom_id`, `gefin_id`
e `tier`. O endpoint de contratos também permite filtrar por status, categoria
de veículo, tipo de operação, mês e texto de busca.

### 3. Iniciar o dashboard

Em outro terminal:

```powershell
cd frontend
npm run dev
```

Abra o endereço exibido pelo Vite, normalmente
`http://localhost:5173`. O dashboard usa a API em
`http://localhost:8000`.

## Estrutura do repositório

```text
bf_geosmart/
├── app/
│   ├── models/          # Modelos Pydantic
│   ├── repositories/    # Acesso às coleções do Cosmos DB
│   ├── routers/         # Rotas da API
│   └── services/        # Regras de negócio
├── frontend/
│   └── src/
│       └── components/  # Mapa, filtros, KPIs e gráficos
├── pipelines/           # Processamento Bronze, Silver e Gold
├── services/
│   ├── database.py      # Conexão e operações em lote no Cosmos DB
│   └── datalake_service.py
├── requirements.txt
└── README.md
```
