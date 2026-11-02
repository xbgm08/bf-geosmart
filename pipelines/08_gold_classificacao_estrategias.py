import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

load_dotenv(override=True)

MONGO_URI = os.getenv("COSMOS_MONGO_URI") or os.getenv("COSMOS_MONGO_CONNECTION_STRING")
DB_NAME = os.getenv("COSMOS_DB_NAME", "bf_geosmart")
COLLECTION_NAME = os.getenv("COSMOS_LOJAS_COLLECTION", "lojas")

# Limites de negócio (Share expresso em pontos percentuais: ex. 18.5 = 18,5%)
SHARE_BAIXO = float(os.getenv("SHARE_BAIXO", "20"))
SHARE_ALTO = float(os.getenv("SHARE_ALTO", "50"))
DESVIO_MAX_ESTAVEL = float(os.getenv("DESVIO_MAX_ESTAVEL", "8"))
QUEDA_MINIMA = float(os.getenv("QUEDA_MINIMA_SHARE", "10"))


def _extrair_mes(registro):
    """Obtém o mês no formato AAAA-MM."""
    for campo in ("mes", "mes_referencia", "ano_mes"):
        valor = registro.get(campo)
        if valor is None:
            continue
        if isinstance(valor, datetime):
            return valor.strftime("%Y-%m")
        texto = str(valor).strip()
        texto = texto[:7]
        try:
            datetime.strptime(texto, "%Y-%m")
            return texto
        except ValueError:
            continue
    return None


def preparar_serie(historico):
    """Valida, converte fração (0 a 1) para percentual (0 a 100) e ordena por mês."""
    if not isinstance(historico, list):
        return []

    por_mes = {}
    for registro in historico:
        if not isinstance(registro, dict):
            continue
        mes = _extrair_mes(registro)

        # Aceita tanto a chave 'share' quanto 'share_estimado'
        valor = registro.get("share")
        if valor is None:
            valor = registro.get("share_estimado")

        if mes is None or valor is None:
            continue
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            continue

        # Se estiver em decimal (ex: 0.65), converte para percentual (65.0)
        if 0 < valor <= 1.0:
            valor = valor * 100.0

        if not 0 <= valor <= 100:
            continue
        por_mes[mes] = valor

    return [(mes, por_mes[mes]) for mes in sorted(por_mes)]


def agrupar_historico_por_gefin(registros):
    """Agrupa o histórico Silver por gefin_id e converte share para percentual."""
    if not isinstance(registros, list):
        return {}

    historicos = {}
    for registro in registros:
        if not isinstance(registro, dict):
            continue
        gefin_id = registro.get("gefin_id")
        if gefin_id is None:
            continue

        valor_bruto = registro.get("share")
        if valor_bruto is None:
            valor_bruto = registro.get("share_estimado")

        try:
            share_percentual = float(valor_bruto)
            if 0 < share_percentual <= 1.0:
                share_percentual = share_percentual * 100.0
        except (TypeError, ValueError):
            continue

        historicos.setdefault(str(gefin_id), []).append(
            {
                "mes_referencia": registro.get("mes_referencia"),
                "share": share_percentual,
            }
        )

    return historicos


def classificar_estrategia(historico):
    """Retorna (estratégia, métricas) ou (None, motivo) se faltar histórico."""
    serie = preparar_serie(historico)
    if len(serie) < 8:
        return None, f"Histórico válido insuficiente: {len(serie)} de 8 meses."

    # Usa os oito meses mais recentes disponíveis
    ultimos_8 = serie[-8:]
    valores = [item[1] for item in ultimos_8]
    meses_analisados = [item[0] for item in ultimos_8]

    media_8 = mean(valores)
    desvio_8 = pstdev(valores)
    media_trimestre = mean(valores[-3:])
    media_cinco_anteriores = mean(valores[:5])
    desvio_cinco_anteriores = pstdev(valores[:5])

    estavel_8 = desvio_8 <= DESVIO_MAX_ESTAVEL
    estavel_passado_alto = (
        media_cinco_anteriores >= SHARE_ALTO
        and desvio_cinco_anteriores <= DESVIO_MAX_ESTAVEL
    )
    trimestre_baixo = media_trimestre < SHARE_BAIXO
    queda_relevante = (
        media_cinco_anteriores - media_trimestre >= QUEDA_MINIMA
    )

    # A prioridade evita conflito entre regras
    if trimestre_baixo and estavel_passado_alto:
        estrategia = "Recuperar"
    elif not estavel_8 and queda_relevante:
        estrategia = "Monitorar"
    elif estavel_8 and media_8 >= SHARE_ALTO:
        estrategia = "Blindar"
    elif estavel_8 and media_8 < SHARE_BAIXO:
        estrategia = "Atacar"
    else:
        estrategia = "Fidelizar"

    metricas = {
        "media_share_8_meses": round(media_8, 2),
        "desvio_padrao_share_8_meses": round(desvio_8, 2),
        "share_estavel_8_meses": estavel_8,
        "media_share_trimestre": round(media_trimestre, 2),
        "meses_analisados": meses_analisados,
        "criterios_configurados": {
            "share_baixo": SHARE_BAIXO,
            "share_alto": SHARE_ALTO,
            "desvio_max_estavel": DESVIO_MAX_ESTAVEL,
            "queda_minima": QUEDA_MINIMA,
        },
    }
    return estrategia, metricas


def executar():
    if not MONGO_URI:
        raise RuntimeError(
            "Defina COSMOS_MONGO_URI (ou COSMOS_MONGO_CONNECTION_STRING) no .env."
        )

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from services.datalake_service import datalake

    print("1. Carregando histórico de share da camada Silver...")
    dados_silver = datalake.download_json("silver", "dados_sinteticos/historico_share.json") or []
    historicos_por_gefin = agrupar_historico_por_gefin(dados_silver)

    cliente = MongoClient(MONGO_URI, serverSelectionTimeoutMS=20000)
    atualizadas = 0
    sem_historico = 0
    sem_alteracao = 0
    nao_encontradas = 0
    exemplos_impressos = 0
    contagem_estrategias = {}

    try:
        cliente.admin.command("ping")
        colecao = cliente[DB_NAME][COLLECTION_NAME]

        print("2. Lendo lojas do Cosmos DB e classificando estratégias comerciais...")
        cursor = colecao.find(
            {},
            {
                "_id": 1,
                "cnpj": 1,
                "razao_social": 1,
                "gefin_id": 1,
                "historico_share": 1,
                "estrategia_comercial": 1,
                "analise_estrategia": 1,
            },
        )

        operacoes = []
        for loja in cursor:
            # Prioriza o histórico salvo na própria loja; se não tiver, usa o do GEFIN na Silver
            historico = loja.get("historico_share")
            if not historico:
                historico = historicos_por_gefin.get(str(loja.get("gefin_id")), [])

            estrategia, resultado = classificar_estrategia(historico)
            if estrategia is None:
                sem_historico += 1
                continue

            contagem_estrategias[estrategia] = contagem_estrategias.get(estrategia, 0) + 1

            # Imprime apenas as 10 primeiras lojas como amostra para não travar o terminal
            if exemplos_impressos < 10:
                print(
                    f" [Amostra] CNPJ: {loja.get('cnpj', 'N/D')} | "
                    f"Loja: {str(loja.get('razao_social', 'N/D'))[:30]} | "
                    f"Média Trim.: {resultado['media_share_trimestre']:.2f}% | "
                    f"Desvio (8m): {resultado['desvio_padrao_share_8_meses']:.2f} p.p. | "
                    f"Estratégia: {estrategia}"
                )
                exemplos_impressos += 1

            if (
                loja.get("estrategia_comercial") == estrategia
                and loja.get("analise_estrategia") == resultado
            ):
                sem_alteracao += 1
                continue

            operacoes.append(
                UpdateOne(
                    {"_id": loja["_id"]},
                    {
                        "$set": {
                            "estrategia_comercial": estrategia,
                            "analise_estrategia": resultado,
                            "estrategia_atualizada_em": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                )
            )

            if len(operacoes) == 500:
                atualizacao = colecao.bulk_write(operacoes, ordered=False)
                atualizadas += atualizacao.modified_count
                sem_alteracao += atualizacao.matched_count - atualizacao.modified_count
                nao_encontradas += len(operacoes) - atualizacao.matched_count
                operacoes.clear()
                print(f" -> Progresso: {atualizadas} lojas atualizadas no Cosmos DB...")
                time.sleep(0.5)

        if operacoes:
            atualizacao = colecao.bulk_write(operacoes, ordered=False)
            atualizadas += atualizacao.modified_count
            sem_alteracao += atualizacao.matched_count - atualizacao.modified_count
            nao_encontradas += len(operacoes) - atualizacao.matched_count

        print("\n=== Resumo da Classificação (Pipeline 08) ===")
        print(f"Documentos modificados: {atualizadas}")
        print(f"Lojas sem histórico suficiente: {sem_historico}")
        print(f"Lojas já com os mesmos valores: {sem_alteracao}")
        print(f"Lojas não encontradas durante atualização: {nao_encontradas}")
        print(f"Distribuição por Estratégia: {contagem_estrategias}")
    finally:
        cliente.close()


if __name__ == "__main__":
    executar()