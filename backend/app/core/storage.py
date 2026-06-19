import os
import uuid
import shutil
from pathlib import Path
from abc import ABC, abstractmethod

from fastapi import UploadFile

from app.config import get_settings

settings = get_settings()


class StorageBackend(ABC):
    """Abstract storage interface — swap LocalStorage for S3Storage without changing callers."""

    @abstractmethod
    async def save(self, file: UploadFile, dest_path: str) -> tuple[str, int]:
        """Save an uploaded file. Returns (absolute_path, size_bytes)."""
        ...

    @abstractmethod
    async def delete(self, artifact_path: str) -> None:
        """Delete a stored artifact."""
        ...

    @abstractmethod
    def get_url(self, artifact_path: str) -> str:
        """Return a URL or path to access the artifact."""
        ...


class LocalStorage(StorageBackend):
    """Stores model artifacts on the local filesystem under ARTIFACT_STORE_PATH."""

    def __init__(self):
        self.base_path = Path(settings.artifact_store_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, file: UploadFile, dest_path: str) -> tuple[str, int]:
        full_path = self.base_path / dest_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        size = 0
        with open(full_path, "wb") as out_file:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                out_file.write(chunk)
                size += len(chunk)

        return str(full_path), size

    async def delete(self, artifact_path: str) -> None:
        path = Path(artifact_path)
        if path.exists():
            path.unlink()
        # Clean up empty parent directory
        try:
            path.parent.rmdir()
        except OSError:
            pass  # directory not empty, that's fine

    def get_url(self, artifact_path: str) -> str:
        # For local storage, just return the filesystem path
        # This will be a container-internal path when running in Docker
        return f"file://{artifact_path}"


def get_storage() -> StorageBackend:
    """Dependency-injectable storage factory. Replace with S3Storage when ready."""
    return LocalStorage()


def build_artifact_path(project_id: uuid.UUID, model_id: uuid.UUID, filename: str) -> str:
    """Build a deterministic storage path: projects/{project_id}/models/{model_id}/{filename}"""
    return f"projects/{project_id}/models/{model_id}/{filename}"
