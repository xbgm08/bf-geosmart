# BF GeoSmart — Redistribuição de Lojas com Dados e Geolocalização

**FATEC Ipiranga — Projeto Integrador IV (Big Data para Negócios)**  

O **BF GeoSmart** é uma solução de Engenharia de Dados, Machine Learning e Inteligência Geográfica desenvolvida para o **Bradesco Financiamentos (BF)**. O sistema apoia a gestão territorial e a redistribuição estratégica de lojas parceiras do setor automotivo dentro da hierarquia comercial do banco: **SUCOM** (Superintendências Comerciais), **GECOM** (Gerências Comerciais Regionais), **GEFIN** (Gerentes de Financiamento) e **Lojas**.

---

## 1. Arquitetura da Solução

A plataforma implementa a arquitetura **Medallion (Bronze, Silver e Gold)** no **Azure Blob Storage (Data Lake)**, combinada com persistência NoSQL orientada a documentos no **Azure Cosmos DB (API para MongoDB)**, um back-end RESTful em **FastAPI** e um dashboard analítico interativo em **React**.

### Fluxo das 7 Pipelines de Dados (Python)
1. **`01_bronze_ingestao_lojas.py` (Camada Bronze):** Extrai ~40.000 empresas únicas via paginação na API pública *Minha Receita*, filtrando 7 CNAEs do setor automotivo com desduplicação de CNPJ em memória.
2. **`02_silver_saneamento_lojas.py` (Camada Silver):** Filtra empresas com situação cadastral ativa (`situacao_cadastral = 2`), descarta MEIs (`opcao_pelo_mei = True`) e padroniza razões sociais, nomes fantasia e endereços.
3. **`03_silver_ingestão_dados_sinteticos.py` (Camada Silver):** Gera a árvore comercial regionalizada (10 SUCOMs, 80 GECOMs e 700 GEFINs com coordenadas GeoJSON por UF), carteiriza as lojas por estado/município e simula séries históricas de propostas, metas e market share via distribuição de Poisson e sazonalidade.
4. **`04_gold_integracao_camadas.py` (Camada Gold & Cosmos DB):** Consolida as bases finais na camada Gold do Data Lake e realiza a ingestão em lotes (`bulk_write` / `insert_many`) no Azure Cosmos DB utilizando o CNPJ como chave primária (`_id = cnpj`) e tratando limites de taxa de transferência (RU/s — código `16500`).
5. **`05_gold_geocodificacao_lojas.py` (Camada Gold & Cosmos DB):** Converte os endereços cadastrais em coordenadas reais no padrão `GeoJSON Point ([longitude, latitude])` via API do *Nominatim (OpenStreetMap)*, utilizando cache em memória e estratégia de fallback em 4 níveis.
6. **`06_gold_kpis_analytics.py` (Camada Gold & Cosmos DB):** Processa com `Pandas` e `NumPy` os indicadores mensais de negócio (VGF pago, metas, atingimento, funil de conversão e estatísticas descritivas), populando as coleções analíticas `kpis_loja_mes` e `kpis_gefin_mes`.
7. **`07_gold_clusterizacao_territorios.py` (Camada Gold & Cosmos DB):** Aplica Machine Learning espacial (`Scikit-Learn` / `NumPy` — Bisseção Espacial e K-Means sobre Latitude e Longitude) para dividir os territórios de forma coesa e equilibrada dentro de cada UF.

---

## 2. Tecnologias Utilizadas

* **Engenharia de Dados & Machine Learning:** Python, Pandas, NumPy, Scikit-Learn, Geopy (Nominatim), Requests, Tqdm, Python-Dotenv.
* **Cloud & Banco de Dados (Microsoft Azure):** Azure Blob Storage (Data Lake Bronze/Silver/Gold) e Azure Cosmos DB for MongoDB (`pymongo`).
* **Back-end API:** FastAPI, Uvicorn, Pydantic (Arquitetura em camadas: *Router -> Service -> Repository*).
* **Front-end Web:** React (Vite), Tailwind CSS, React-Leaflet / Leaflet (renderização HTML5 Canvas), Recharts, Axios, Lucide React.

---

## 3. Pré-requisitos e Configuração do Ambiente

### 3.1. Variáveis de Ambiente (`.env`)
Crie um arquivo `.env` na raiz do projeto contendo as credenciais do Azure Data Lake e do Azure Cosmos DB:

```env
# Azure Blob Storage (Data Lake)
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"

# Azure Cosmos DB (API MongoDB)
COSMOS_MONGO_URI="mongodb://..."
COSMOS_DB_NAME="bf_geosmart"
```

### 3.2. Instalação das Dependências do Back-end e Pipelines
Na raiz do projeto, crie e ative um ambiente virtual Python e instale os pacotes necessários:

```bash
python -m venv .venv

# Ativação no Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Ativação no Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

---

## 4. Como Executar as Pipelines de Dados

Execute os scripts na ordem sequencial abaixo a partir da raiz do projeto:

```bash
# 1. Ingestão bruta da API Minha Receita (40.000 CNPJs únicos -> Bronze)
python pipelines/01_bronze_ingestao_lojas.py

# 2. Saneamento de empresas ativas e exclusão de MEIs (Bronze -> Silver)
python pipelines/02_silver_saneamento_lojas.py

# 3. Geração da hierarquia (SUCOM/GECOM/GEFIN) e dados sintéticos (Silver)
python pipelines/03_silver_ingestão_dados_sinteticos.py

# 4. Consolidação na camada Gold e carga em lotes no Azure Cosmos DB
python pipelines/04_gold_integracao_camadas.py

# 5. Geocodificação espacial via Nominatim/OpenStreetMap (requer internet)
python pipelines/05_gold_geocodificacao_lojas.py

# 6. Cálculo de KPIs mensais por Loja e por GEFIN (Pandas/NumPy)
python pipelines/06_gold_kpis_analytics.py

# 7. Clusterização territorial K-Means espacial (Scikit-Learn)
python pipelines/07_gold_clusterizacao_territorios.py
```

---

## 5. Como Executar a Aplicação Web (API + Dashboard)

### 5.1. Iniciar o Back-end (FastAPI)
Em um terminal com o ambiente virtual ativado:

```bash
uvicorn app.main:app --reload
```
* A documentação interativa da API (Swagger UI) estará disponível em: `http://localhost:8000/docs`

### 5.2. Iniciar o Front-end (React + Vite)
Em um segundo terminal, acesse a pasta do front-end, instale as dependências Node.js e inicie o servidor de desenvolvimento:

```bash
cd frontend
npm install
npm run dev
```
* Acesse o dashboard executivo no navegador pelo endereço exibido no terminal (por padrão: `http://localhost:5173`).

---