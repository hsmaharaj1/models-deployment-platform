"""
inference_tasks.py — Celery tasks for async model inference.

Architecture:
  1. FastAPI route creates an InferenceJob row (status=queued) and enqueues this task.
  2. This task runs in the Celery worker process (not the API process).
  3. It opens its own DB connection (sync SQLAlchemy, since Celery is sync).
  4. It calls the running inference container via httpx (sync).
  5. It writes the result back to the InferenceJob row.
"""
import time
import uuid
from datetime import datetime, timezone

import httpx
from celery import Task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.inference_job import InferenceJob, JobStatus
from app.models.deployment import Deployment, DeploymentStatus
from app.workers.celery_app import celery_app
from app.routers.metrics import record_inference

settings = get_settings()

# Sync engine for Celery worker (asyncpg → psycopg2 driver swap)
_SYNC_DB_URL = settings.database_url.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)
_engine = create_engine(_SYNC_DB_URL, pool_pre_ping=True, pool_size=5)


def _get_session() -> Session:
    return Session(_engine)


@celery_app.task(
    name="inference.run",
    bind=True,
    max_retries=0,          # Don't auto-retry — bad payloads would retry forever
    acks_late=True,
)
def run_inference(self: Task, job_id: str) -> dict:
    """
    Execute an async inference job:
      1. Load the job + deployment from DB
      2. POST inputs to the inference container
      3. Write result back to the job row
    """
    with _get_session() as db:
        # ── Load job ──────────────────────────────────────────────────
        job = db.get(InferenceJob, uuid.UUID(job_id))
        if not job:
            return {"error": f"Job {job_id} not found"}

        deployment = db.get(Deployment, job.deployment_id)
        if not deployment or deployment.status != DeploymentStatus.running:
            _fail(db, job, "Deployment is not running")
            return {"error": "Deployment not running"}

        # ── Mark processing ───────────────────────────────────────────
        job.status = JobStatus.processing
        db.commit()

        # ── Call inference container ──────────────────────────────────
        predict_url = f"{deployment.endpoint_url}/predict"
        t0 = time.perf_counter()

        try:
            resp = httpx.post(
                predict_url,
                json={"inputs": job.input_payload.get("inputs", [])},
                timeout=30.0,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            record_inference(str(deployment.id), 0.0, is_error=True)
            _fail(db, job, f"Container unreachable: {e}")
            return {"error": str(e)}

        latency_ms = round((time.perf_counter() - t0) * 1000, 3)

        if resp.status_code != 200:
            record_inference(str(deployment.id), latency_ms, is_error=True)
            _fail(db, job, f"Container returned {resp.status_code}: {resp.text[:200]}")
            return {"error": resp.text}

        result = resp.json()
        record_inference(str(deployment.id), latency_ms, is_error=False)

        # ── Write result ──────────────────────────────────────────────
        job.status = JobStatus.completed
        job.output_payload = result
        job.latency_ms = latency_ms
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        return {"job_id": job_id, "predictions": result.get("predictions"), "latency_ms": latency_ms}


def _fail(db: Session, job: InferenceJob, reason: str) -> None:
    job.status = JobStatus.failed
    job.error_message = reason[:500]
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
