"""
Storage layer: MinIO mock para simulação de object storage.
Gerencia upload/download de PDFs, resultados de OCR e chunks extraídos.
"""

import json
import io
from datetime import timedelta
from minio import Minio
from minio.error import S3Error

from app.config.settings import settings


class StorageClient:
    def __init__(self):
        self.client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Garante que o bucket existe."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            raise RuntimeError(f"Erro ao inicializar bucket MinIO: {e}")

    def upload_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Faz upload de bytes para o MinIO e retorna o caminho no bucket."""
        stream = io.BytesIO(data)
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_key,
            data=stream,
            length=len(data),
            content_type=content_type,
        )
        return f"minio://{self.bucket}/{object_key}"

    def upload_json(self, object_key: str, payload: dict) -> str:
        """Serializa dict para JSON e faz upload."""
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return self.upload_bytes(object_key, raw, content_type="application/json")

    def upload_text(self, object_key: str, text: str) -> str:
        """Faz upload de texto puro (markdown, etc.)."""
        raw = text.encode("utf-8")
        return self.upload_bytes(
            object_key, raw, content_type="text/plain; charset=utf-8"
        )

    def upload_file(self, object_key: str, file_path: str) -> str:
        """Faz upload de arquivo local."""
        self.client.fput_object(
            bucket_name=self.bucket,
            object_name=object_key,
            file_path=file_path,
        )
        return f"minio://{self.bucket}/{object_key}"

    def download_bytes(self, object_key: str) -> bytes:
        """Baixa objeto e retorna como bytes."""
        response = self.client.get_object(self.bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()

    def download_json(self, object_key: str) -> dict:
        """Baixa e desserializa JSON."""
        raw = self.download_bytes(object_key)
        return json.loads(raw.decode("utf-8"))

    def download_text(self, object_key: str) -> str:
        """Baixa e retorna texto."""
        return self.download_bytes(object_key).decode("utf-8")

    def get_presigned_url(self, object_key: str, expires_hours: int = 24) -> str:
        """Gera URL pré-assinada para acesso temporário."""
        url = self.client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=object_key,
            expires=timedelta(hours=expires_hours),
        )
        return url

    def object_exists(self, object_key: str) -> bool:
        """Verifica se objeto existe no bucket."""
        try:
            self.client.stat_object(self.bucket, object_key)
            return True
        except S3Error:
            return False

    def list_objects(self, prefix: str) -> list[str]:
        """Lista objetos com determinado prefixo."""
        objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objects]


storage = StorageClient()
