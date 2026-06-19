from datetime import datetime
from pydantic import BaseModel
from app.models.model_version import ModelFramework, ModelStatus


class ModelVersionCreate(BaseModel):
    version_tag: str
    framework: ModelFramework
    description: str | None = None
    metadata_json: dict | None = None


class ModelVersionUpdate(BaseModel):
    description: str | None = None
    status: ModelStatus | None = None
    metadata_json: dict | None = None


class ModelVersionResponse(BaseModel):
    id: str
    project_id: str
    version_tag: str
    framework: ModelFramework
    original_filename: str
    file_size_bytes: int | None
    description: str | None
    metadata_json: dict | None
    status: ModelStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
