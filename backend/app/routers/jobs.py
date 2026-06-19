"""
jobs.py — Async inference job router.

Two endpoints:
  POST /deployments/{id}/predict/async  → enqueue job, return job_id immediately
  GET  /jobs/{job_id}                   → poll job status + result
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user
from app.database import get_db
from app.models.deployment import Deployment, DeploymentStatus
from app.models.inference_job import InferenceJob, JobStatus
from app.models.user import User
from app.schemas.inference import InferenceRequest
from app.workers.inference_tasks import run_inference

router = APIRouter(tags=["async-inference"])


# ── Submit async job ──────────────────────────────────────────────────────────
@router.post("/deployments/{deployment_id}/predict/async", status_code=202)
async def submit_async_job(
    deployment_id: uuid.UUID,
    payload: InferenceRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Enqueue an async inference job. Returns immediately with a job_id.
    Poll GET /jobs/{job_id} for the result.
    """
    result = await db.execute(
        select(Deployment).where(Deployment.id == deployment_id)
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    if deployment.status != DeploymentStatus.running:
        raise HTTPException(
            status_code=409,
            detail=f"Deployment is not running (status: {deployment.status.value})",
        )

    # Create job record
    job = InferenceJob(
        deployment_id=deployment_id,
        input_payload={"inputs": payload.inputs},
        status=JobStatus.queued,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Enqueue Celery task — commit first so the worker can find the job row
    await db.commit()
    task = run_inference.delay(str(job.id))

    # Store celery task ID for cross-reference
    job.celery_task_id = task.id
    db.add(job)
    await db.commit()

    return {
        "job_id": str(job.id),
        "celery_task_id": task.id,
        "status": job.status.value,
        "deployment_id": str(deployment_id),
    }


# ── Poll job status ───────────────────────────────────────────────────────────
@router.get("/jobs/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return current status and result (if completed) of an async inference job."""
    result = await db.execute(
        select(InferenceJob).where(InferenceJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": str(job.id),
        "deployment_id": str(job.deployment_id),
        "celery_task_id": job.celery_task_id,
        "status": job.status.value,
        "input_payload": job.input_payload,
        "output_payload": job.output_payload,
        "latency_ms": job.latency_ms,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


# ── List jobs for a deployment ────────────────────────────────────────────────
@router.get("/deployments/{deployment_id}/jobs")
async def list_jobs(
    deployment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List the 20 most recent inference jobs for a deployment."""
    result = await db.execute(
        select(InferenceJob)
        .where(InferenceJob.deployment_id == deployment_id)
        .order_by(InferenceJob.created_at.desc())
        .limit(20)
    )
    jobs = result.scalars().all()
    return [
        {
            "job_id": str(j.id),
            "status": j.status.value,
            "latency_ms": j.latency_ms,
            "error_message": j.error_message,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in jobs
    ]
