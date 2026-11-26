import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from azure.servicebus import ServiceBusClient, ServiceBusMessage

load_dotenv(override=True)


class PubSubService:
    def __init__(self):
        self.connection_string = os.getenv("AZURE_SERVICEBUS_CONNECTION_STRING")
        self.topico_padrao = os.getenv("AZURE_SERVICEBUS_TOPIC", "eventos-lojas")

    def publicar_evento(self, tipo_evento: str, dados: dict, topico: str = None):
        """Publica uma mensagem JSON no tópico do Azure Service Bus."""
        if not self.connection_string:
            print("[Pub/Sub] Aviso: AZURE_SERVICEBUS_CONNECTION_STRING não configurada.")
            return False

        nome_topico = topico or self.topico_padrao
        envelope = {
            "tipo_evento": tipo_evento,
            "data_hora": datetime.now(timezone.utc).isoformat(),
            "dados": dados,
        }

        with ServiceBusClient.from_connection_string(self.connection_string) as cliente:
            enviador = cliente.get_topic_sender(topic_name=nome_topico)
            with enviador:
                mensagem = ServiceBusMessage(json.dumps(envelope, ensure_ascii=False))
                enviador.send_messages(mensagem)

        print(f"[Pub/Sub] Evento '{tipo_evento}' publicado no tópico '{nome_topico}'.")
        return True


pubsub_service = PubSubService()