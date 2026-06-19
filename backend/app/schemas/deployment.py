from datetime import datetime
from typing import Any
from pydantic import BaseModel
from app.models.deployment import DeploymentStatus


class DeploymentCreate(BaseModel):
    name: str


class DeploymentResponse(BaseModel):
    id: str
    model_version_id: str
    name: str
    container_id: str | None
    endpoint_url: str | None
    port: int | None
    status: DeploymentStatus
    created_at: datetime
    stopped_at: datetime | None

    model_config = {"from_attributes": True}


class DeploymentDetailResponse(DeploymentResponse):
    model_version: dict[str, Any] | None = None

