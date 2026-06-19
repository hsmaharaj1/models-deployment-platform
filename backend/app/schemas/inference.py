from datetime import datetime
from pydantic import BaseModel
from app.models.inference_job import JobStatus


class InferenceRequest(BaseModel):
    inputs: list[list[float]]  # Array of arrays for tabular data


class InferenceResponse(BaseModel):
    predictions: list
    latency_ms: float


class JobResponse(BaseModel):
    id: str
    deployment_id: str
    celery_task_id: str | None
    status: JobStatus
    input_payload: dict | None
    output_payload: dict | None
    latency_ms: float | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class JobSubmitResponse(BaseModel):
    job_id: str
    status: JobStatus
