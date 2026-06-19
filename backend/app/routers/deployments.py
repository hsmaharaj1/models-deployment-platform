import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.deployment import Deployment, DeploymentStatus
from app.models.model_version import ModelVersion
from app.schemas.deployment import DeploymentCreate, DeploymentResponse, DeploymentDetailResponse
from app.core.auth import get_current_user
from app.services.deployment_service import get_deployment_service

router = APIRouter(prefix="/deployments", tags=["deployments"])


async def get_deployment_or_404(deployment_id: uuid.UUID, db: AsyncSession) -> Deployment:
    result = await db.execute(
        select(Deployment)
        .where(Deployment.id == deployment_id)
        .options(selectinload(Deployment.model_version))
    )
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return dep


# ── Deploy a model version ──────────────────────────────────────────
@router.post(
    "/models/{model_id}/deploy",
    response_model=DeploymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["deployments"],
)
async def deploy_model(
    model_id: uuid.UUID,
    payload: DeploymentCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Deploy a model version. Returns 202 immediately — container startup
    runs asynchronously. Poll GET /deployments/{id} for status updates.
    """
    result = await db.execute(select(ModelVersion).where(ModelVersion.id == model_id))
    model_version = result.scalar_one_or_none()
    if not model_version:
        raise HTTPException(status_code=404, detail="Model version not found")

    service = get_deployment_service()
    deployment = await service.deploy(model_version=model_version, name=payload.name, db=db)

    # CRITICAL: commit before add_task so the background task's fresh DB session
    # can see the deployment row (background tasks run in a new session).
    await db.commit()

    # Schedule container startup as a background task
    background_tasks.add_task(service.start_container_background, deployment.id)

    return DeploymentResponse(
        id=str(deployment.id),
        model_version_id=str(deployment.model_version_id),
        name=deployment.name,
        container_id=deployment.container_id,
        endpoint_url=deployment.endpoint_url,
        port=deployment.port,
        status=deployment.status,
        created_at=deployment.created_at,
        stopped_at=deployment.stopped_at,
    )


# ── List all deployments ────────────────────────────────────────────
@router.get("", response_model=list[DeploymentDetailResponse])
async def list_deployments(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Deployment)
        .options(selectinload(Deployment.model_version))
        .order_by(Deployment.created_at.desc())
    )
    deployments = result.scalars().all()

    return [
        DeploymentDetailResponse(
            id=str(d.id),
            model_version_id=str(d.model_version_id),
            name=d.name,
            container_id=d.container_id,
            endpoint_url=d.endpoint_url,
            port=d.port,
            status=d.status,
            created_at=d.created_at,
            stopped_at=d.stopped_at,
            model_version={
                "id": str(d.model_version.id),
                "version_tag": d.model_version.version_tag,
                "framework": d.model_version.framework.value,
                "original_filename": d.model_version.original_filename,
                "status": d.model_version.status.value,
                "project_id": str(d.model_version.project_id),
            } if d.model_version else None,
        )
        for d in deployments
    ]


# ── Get single deployment ───────────────────────────────────────────
@router.get("/{deployment_id}", response_model=DeploymentDetailResponse)
async def get_deployment(
    deployment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    dep = await get_deployment_or_404(deployment_id, db)

    return DeploymentDetailResponse(
        id=str(dep.id),
        model_version_id=str(dep.model_version_id),
        name=dep.name,
        container_id=dep.container_id,
        endpoint_url=dep.endpoint_url,
        port=dep.port,
        status=dep.status,
        created_at=dep.created_at,
        stopped_at=dep.stopped_at,
        model_version={
            "id": str(dep.model_version.id),
            "version_tag": dep.model_version.version_tag,
            "framework": dep.model_version.framework.value,
            "original_filename": dep.model_version.original_filename,
            "status": dep.model_version.status.value,
            "project_id": str(dep.model_version.project_id),
        } if dep.model_version else None,
    )


# ── Stop a deployment ───────────────────────────────────────────────
@router.post("/{deployment_id}/stop", response_model=DeploymentResponse)
async def stop_deployment(
    deployment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    dep = await get_deployment_or_404(deployment_id, db)

    if dep.status == DeploymentStatus.stopped:
        raise HTTPException(status_code=400, detail="Deployment is already stopped")
    if dep.status == DeploymentStatus.failed:
        raise HTTPException(status_code=400, detail="Deployment already failed")

    service = get_deployment_service()
    dep = await service.stop(dep, db)

    return DeploymentResponse(
        id=str(dep.id),
        model_version_id=str(dep.model_version_id),
        name=dep.name,
        container_id=dep.container_id,
        endpoint_url=dep.endpoint_url,
        port=dep.port,
        status=dep.status,
        created_at=dep.created_at,
        stopped_at=dep.stopped_at,
    )


# ── Rollback ────────────────────────────────────────────────────────
@router.post("/{deployment_id}/rollback", response_model=DeploymentResponse, status_code=202)
async def rollback_deployment(
    deployment_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Stop the current deployment and create a new one for the previous model version.
    """
    dep = await get_deployment_or_404(deployment_id, db)

    if dep.status not in [DeploymentStatus.running, DeploymentStatus.failed]:
        raise HTTPException(
            status_code=400,
            detail="Only running or failed deployments can be rolled back",
        )

    service = get_deployment_service()
    try:
        new_dep = await service.rollback(dep, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()  # Commit before background task runs

    background_tasks.add_task(service.start_container_background, new_dep.id)

    return DeploymentResponse(
        id=str(new_dep.id),
        model_version_id=str(new_dep.model_version_id),
        name=new_dep.name,
        container_id=new_dep.container_id,
        endpoint_url=new_dep.endpoint_url,
        port=new_dep.port,
        status=new_dep.status,
        created_at=new_dep.created_at,
        stopped_at=new_dep.stopped_at,
    )


# ── Get container logs ──────────────────────────────────────────────
@router.get("/{deployment_id}/logs")
async def get_deployment_logs(
    deployment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    dep = await get_deployment_or_404(deployment_id, db)

    if not dep.container_id:
        return {"logs": "No container started yet"}

    from app.core.docker_manager import get_docker_manager
    dm = get_docker_manager()
    logs = dm.get_container_logs(dep.container_id)
    return {"logs": logs}


# ── Recover stuck deployment ────────────────────────────────────────
@router.post("/{deployment_id}/recover", response_model=DeploymentResponse)
async def recover_deployment(
    deployment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Re-check if a starting/failed deployment's container is actually healthy
    and promote it to 'running'. Useful after the background task health-check
    timed out (e.g. on first Docker image pull).
    """
    from app.core.docker_manager import get_docker_manager
    from app.config import get_settings
    import httpx

    dep = await get_deployment_or_404(deployment_id, db)

    if dep.status not in [DeploymentStatus.starting, DeploymentStatus.failed]:
        raise HTTPException(
            status_code=400,
            detail=f"Deployment status is '{dep.status.value}' — only 'starting' or 'failed' can be recovered"
        )

    if not dep.port:
        raise HTTPException(status_code=400, detail="Deployment has no port assigned")

    settings = get_settings()
    url = f"http://{settings.inference_host}:{dep.port}/health"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
        is_healthy = resp.status_code == 200
    except Exception:
        is_healthy = False

    if is_healthy:
        dep.status = DeploymentStatus.running
        dep.endpoint_url = f"http://{settings.inference_host}:{dep.port}"
        await db.commit()
    else:
        raise HTTPException(
            status_code=503,
            detail=f"Container at {url} is not responding with HTTP 200"
        )

    return DeploymentResponse(
        id=str(dep.id),
        model_version_id=str(dep.model_version_id),
        name=dep.name,
        container_id=dep.container_id,
        endpoint_url=dep.endpoint_url,
        port=dep.port,
        status=dep.status,
        created_at=dep.created_at,
        stopped_at=dep.stopped_at,
    )

