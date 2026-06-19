"""
Inference router — proxies prediction requests to the running inference container.
Also provides sync predict directly through the platform API.
"""
import time
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.deployment import Deployment, DeploymentStatus
from app.schemas.inference import InferenceRequest, InferenceResponse
from app.core.auth import get_current_user
from app.routers.metrics import record_inference

router = APIRouter(tags=["inference"])


@router.post("/deployments/{deployment_id}/predict", response_model=InferenceResponse)
async def predict(
    deployment_id: uuid.UUID,
    payload: InferenceRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Synchronous inference: proxy the request to the running inference container
    and return the prediction. The platform adds its own latency measurement
    on top of the container's reported latency.
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
            detail=f"Deployment is not running (current status: {deployment.status.value})",
        )

    if not deployment.endpoint_url:
        raise HTTPException(status_code=503, detail="Deployment has no endpoint URL")

    predict_url = f"{deployment.endpoint_url}/predict"
    t0 = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                predict_url,
                json={"inputs": payload.inputs},
            )
    except httpx.ConnectError:
        record_inference(str(deployment_id), 0.0, is_error=True)
        raise HTTPException(
            status_code=503,
            detail="Cannot reach inference container. It may have crashed.",
        )
    except httpx.TimeoutException:
        record_inference(str(deployment_id), 30_000.0, is_error=True)
        raise HTTPException(status_code=504, detail="Inference container timed out after 30s")

    platform_latency_ms = (time.perf_counter() - t0) * 1000

    if resp.status_code != 200:
        record_inference(str(deployment_id), round(platform_latency_ms, 3), is_error=True)
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Inference container error: {resp.text[:500]}",
        )

    data = resp.json()
    record_inference(str(deployment_id), round(platform_latency_ms, 3), is_error=False)
    return InferenceResponse(
        predictions=data.get("predictions", []),
        latency_ms=round(platform_latency_ms, 3),
    )
