"""
DeploymentService — business logic for the full deployment lifecycle.

State machine:
  pending → starting → running
                    ↘ failed
  running → stopped

The deploy() method returns immediately after creating the DB record.
The actual container startup runs as a FastAPI background task so the
HTTP response is not blocked by Docker operations.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.docker_manager import get_docker_manager, PORT_RANGE_START, PORT_RANGE_END
from app.database import AsyncSessionLocal
from app.models.deployment import Deployment, DeploymentStatus
from app.models.model_version import ModelVersion
from app.config import get_settings

logger = logging.getLogger("deployment_service")
settings = get_settings()

# Host used to reach inference containers — 'localhost' for local dev,
# override via INFERENCE_HOST env var when running inside Docker
INFERENCE_HOST = settings.inference_host


class DeploymentService:

    async def get_used_ports(self, db: AsyncSession) -> list[int]:
        """Return all ports currently occupied by non-stopped deployments."""
        result = await db.execute(
            select(Deployment.port).where(
                Deployment.port.is_not(None),
                Deployment.status.in_([
                    DeploymentStatus.pending,
                    DeploymentStatus.starting,
                    DeploymentStatus.running,
                ])
            )
        )
        return [r for (r,) in result.all() if r is not None]

    async def deploy(
        self,
        model_version: ModelVersion,
        name: str,
        db: AsyncSession,
    ) -> Deployment:
        """
        Create a Deployment record (status=pending) and return it immediately.
        Container startup is delegated to a background task.
        """
        dm = get_docker_manager()
        used_ports = await self.get_used_ports(db)
        port = dm.find_free_port(used_ports)

        deployment = Deployment(
            model_version_id=model_version.id,
            name=name,
            port=port,
            status=DeploymentStatus.pending,
        )
        db.add(deployment)
        await db.flush()
        await db.refresh(deployment)
        return deployment

    async def start_container_background(self, deployment_id: uuid.UUID) -> None:
        """
        Background task: actually spin up the Docker container and update status.
        Creates its own DB session (can't reuse the request session).
        """
        dm = get_docker_manager()

        async with AsyncSessionLocal() as db:
            try:
                # Fetch deployment + model version
                result = await db.execute(
                    select(Deployment).where(Deployment.id == deployment_id)
                )
                deployment = result.scalar_one_or_none()
                if not deployment:
                    logger.error(f"Deployment {deployment_id} not found in background task")
                    return

                result2 = await db.execute(
                    select(ModelVersion).where(ModelVersion.id == deployment.model_version_id)
                )
                model_version = result2.scalar_one_or_none()
                if not model_version:
                    await self._mark_failed(db, deployment, "Model version not found")
                    return

                # → starting
                deployment.status = DeploymentStatus.starting
                await db.commit()

                # Start Docker container
                try:
                    container = await asyncio.to_thread(
                        dm.start_inference_container,
                        str(deployment_id),
                        model_version.framework.value,
                        model_version.artifact_path,
                        deployment.port,
                    )
                    deployment.container_id = container.id
                    await db.commit()
                except Exception as e:
                    logger.error(f"Failed to start container for {deployment_id}: {e}")
                    await self._mark_failed(db, deployment, str(e))
                    return

                # Poll health
                healthy = await dm.wait_until_healthy(
                    host_port=deployment.port,
                    max_wait_seconds=90,
                    inference_host=INFERENCE_HOST,
                )

                if healthy:
                    deployment.status = DeploymentStatus.running
                    deployment.endpoint_url = (
                        f"http://{INFERENCE_HOST}:{deployment.port}"
                    )
                    await db.commit()
                    logger.info(
                        f"Deployment {deployment_id} running at {deployment.endpoint_url}"
                    )
                else:
                    # Container started but never became healthy — grab logs
                    logs = ""
                    if deployment.container_id:
                        logs = dm.get_container_logs(deployment.container_id, tail=30)
                    await self._mark_failed(
                        db, deployment,
                        f"Container did not become healthy within 90s.\nLogs:\n{logs}"
                    )
                    # Clean up the unhealthy container
                    if deployment.container_id:
                        try:
                            await asyncio.to_thread(
                                dm.stop_and_remove_container, deployment.container_id
                            )
                        except Exception:
                            pass

            except Exception as e:
                logger.exception(f"Unhandled error in deployment background task: {e}")

    async def stop(self, deployment: Deployment, db: AsyncSession) -> Deployment:
        """Stop a running deployment: kill container and mark stopped."""
        dm = get_docker_manager()

        if deployment.container_id:
            try:
                await asyncio.to_thread(
                    dm.stop_and_remove_container, deployment.container_id
                )
            except Exception as e:
                logger.warning(f"Container stop error (continuing): {e}")

        deployment.status = DeploymentStatus.stopped
        deployment.stopped_at = datetime.now(timezone.utc)
        await db.flush()
        return deployment

    async def rollback(
        self,
        deployment: Deployment,
        db: AsyncSession,
    ) -> Deployment:
        """
        Rollback: stop the current deployment and create a new one for the
        immediately previous model version in the same project.
        Returns the NEW deployment record.
        """
        # Fetch the current model version's project_id without touching lazy relationship
        mv_result = await db.execute(
            select(ModelVersion.project_id).where(ModelVersion.id == deployment.model_version_id)
        )
        row = mv_result.one_or_none()
        if not row:
            raise ValueError("Current model version not found")
        project_id = row[0]

        # Find all model versions in this project, sorted newest-first
        result = await db.execute(
            select(ModelVersion)
            .where(ModelVersion.project_id == project_id)
            .order_by(ModelVersion.created_at.desc())
        )
        versions = result.scalars().all()

        # Find the index of the currently deployed version
        current_ids = [str(v.id) for v in versions]
        try:
            current_idx = current_ids.index(str(deployment.model_version_id))
        except ValueError:
            raise ValueError("Current model version not found in project")

        if current_idx + 1 >= len(versions):
            raise ValueError("No previous version to roll back to")

        previous_version = versions[current_idx + 1]

        # Stop current
        await self.stop(deployment, db)

        # Deploy previous version
        new_deployment = await self.deploy(
            model_version=previous_version,
            name=f"{deployment.name}-rollback",
            db=db,
        )
        return new_deployment

    @staticmethod
    async def _mark_failed(
        db: AsyncSession, deployment: Deployment, reason: str
    ) -> None:
        deployment.status = DeploymentStatus.failed
        deployment.stopped_at = datetime.now(timezone.utc)
        logger.error(f"Deployment {deployment.id} failed: {reason[:200]}")
        await db.commit()


# Module-level singleton
_service: DeploymentService | None = None


def get_deployment_service() -> DeploymentService:
    global _service
    if _service is None:
        _service = DeploymentService()
    return _service
