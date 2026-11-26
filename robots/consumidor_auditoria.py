import json
import os
from dotenv import load_dotenv
from azure.servicebus import ServiceBusClient
from services.database import cosmos_db

load_dotenv(override=True)


def iniciar_consumidor():
    connection_string = os.getenv("AZURE_SERVICEBUS_CONNECTION_STRING")
    topico = os.getenv("AZURE_SERVICEBUS_TOPIC", "eventos-lojas")
    assinatura = "sub-auditoria"

    colecao_auditoria = cosmos_db.obter_colecao("auditoria_eventos")
    print(f"Escutando tópico '{topico}' na assinatura '{assinatura}'... (Ctrl+C para parar)")

    with ServiceBusClient.from_connection_string(connection_string) as cliente:
        receptor = cliente.get_subscription_receiver(
            topic_name=topico,
            subscription_name=assinatura,
        )
        with receptor:
            for mensagem in receptor:
                conteudo = json.loads(str(mensagem))
                print(f" -> Evento recebido: {conteudo['tipo_evento']} | Dados: {conteudo['dados']}")

                # Salva o evento na coleção de auditoria do Cosmos DB
                colecao_auditoria.insert_one(conteudo)

                # Confirma para o Azure Service Bus que a mensagem foi processada
                receptor.complete_message(mensagem)


if __name__ == "__main__":
    iniciar_consumidor()