import os
import json
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

load_dotenv()

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

class DataLakeService:
    def __init__(self):
        if not CONNECTION_STRING:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING não configurada no .env")
        
        self.blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)

    def upload_json(self, container_name: str, blob_path: str, data: list | dict):
        """Faz upload de dados estruturados em JSON diretamente para o container."""
        container_client = self.blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_path)
        
        # Converte o dicionário/lista Python para bytes JSON
        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        blob_client.upload_blob(json_bytes, overwrite=True)
        print(f"[Data Lake] Sucesso: '{blob_path}' salvo no container '{container_name}'.")

    def download_json(self, container_name: str, blob_path: str) -> list | dict:
        """Lê um arquivo JSON do container e retorna como lista/dicionário Python."""
        container_client = self.blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_path)
        
        stream = blob_client.download_blob()
        return json.loads(stream.readall().decode("utf-8"))

# Instância global pronta para ser importada pelos scripts ETL
datalake = DataLakeService()