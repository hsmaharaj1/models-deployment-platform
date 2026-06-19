"""
DockerManager — wraps the Docker SDK for managing inference containers.

Design decisions:
- Each deployment gets its own isolated container (no shared runtimes)
- Ports are allocated dynamically from HOST_PORT_RANGE (9000-9099)
- Model artifacts are bind-mounted from the host artifact store
- Container names are deterministic: mlplatform-{deployment_id}
- Health polling uses exponential backoff
"""
import asyncio
import logging
import os
from pathlib import Path

import docker
import docker.errors
from docker.models.containers import Container

from app.config import get_settings

logger = logging.getLogger("docker_manager")
settings = get_settings()

# Inference image names (built from inference-servers/)
INFERENCE_IMAGES = {
    "sklearn": "mlplatform-sklearn-server:latest",
    "pytorch": "mlplatform-torch-server:latest",
}

# Port pool for inference containers
PORT_RANGE_START = 9000
PORT_RANGE_END = 9099

# Path inside every inference container where artifacts are mounted
CONTAINER_ARTIFACTS_MOUNT = "/app/artifacts"


class DockerManager:
    def __init__(self):
        self._client: docker.DockerClient | None = None

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    # ── Port allocation ────────────────────────────────────────────────
    def find_free_port(self, used_ports: list[int]) -> int:
        """Return the first port in PORT_RANGE that isn't in used_ports."""
        used = set(used_ports)
        for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
            if port not in used:
                return port
        raise RuntimeError(
            f"No free ports available in range {PORT_RANGE_START}-{PORT_RANGE_END}. "
            "Stop some deployments first."
        )

    # ── Container lifecycle ────────────────────────────────────────────
    def start_inference_container(
        self,
        deployment_id: str,
        framework: str,
        artifact_path: str,
        host_port: int,
    ) -> Container:
        """
        Start an inference container for the given model.

        Args:
            deployment_id: Used as container name suffix
            framework: 'sklearn' or 'pytorch'
            artifact_path: Absolute path to the model file ON THE HOST
            host_port: Port on the host to bind the container's 8080 to

        Returns:
            The running Docker container object
        """
        image = INFERENCE_IMAGES.get(framework)
        if not image:
            raise ValueError(f"Unknown framework: {framework}. Supported: {list(INFERENCE_IMAGES)}")

        # Compute the artifact store base and the relative model path
        artifact_store_base = settings.artifact_store_abs_path
        artifact_abs = str(Path(artifact_path).resolve())

        # Determine the model path inside the container
        if artifact_abs.startswith(artifact_store_base):
            relative = artifact_abs[len(artifact_store_base):].lstrip("/")
            model_path_in_container = f"{CONTAINER_ARTIFACTS_MOUNT}/{relative}"
        else:
            # Fallback: mount the file's directory directly
            artifact_store_base = str(Path(artifact_abs).parent)
            model_path_in_container = f"{CONTAINER_ARTIFACTS_MOUNT}/{Path(artifact_abs).name}"

        container_name = f"mlplatform-{deployment_id}"
        logger.info(
            f"Starting container {container_name} | image={image} | port={host_port} | model={model_path_in_container}"
        )

        container = self.client.containers.run(
            image=image,
            name=container_name,
            detach=True,
            remove=False,  # We remove explicitly on stop so we can inspect logs
            environment={
                "MODEL_PATH": model_path_in_container,
                "PORT": "8080",
            },
            volumes={
                artifact_store_base: {
                    "bind": CONTAINER_ARTIFACTS_MOUNT,
                    "mode": "ro",  # read-only — containers cannot modify artifacts
                }
            },
            ports={"8080/tcp": host_port},
        )

        logger.info(f"Container started: {container.id[:12]}")
        return container

    def stop_and_remove_container(self, container_id: str) -> None:
        """Stop and remove a container by ID. Idempotent — ignores not-found errors."""
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=10)
            container.remove(force=True)
            logger.info(f"Container {container_id[:12]} stopped and removed")
        except docker.errors.NotFound:
            logger.warning(f"Container {container_id[:12]} not found (already removed?)")
        except Exception as e:
            logger.error(f"Error stopping container {container_id[:12]}: {e}")
            raise

    def get_container_status(self, container_id: str) -> str:
        """Return container status string or 'not_found'."""
        try:
            container = self.client.containers.get(container_id)
            container.reload()
            return container.status  # 'running', 'exited', 'created', etc.
        except docker.errors.NotFound:
            return "not_found"

    def get_container_logs(self, container_id: str, tail: int = 50) -> str:
        """Return last N lines of container stdout+stderr logs."""
        try:
            container = self.client.containers.get(container_id)
            return container.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")
        except docker.errors.NotFound:
            return "Container not found"
        except Exception as e:
            return f"Error fetching logs: {e}"

    # ── Health polling ─────────────────────────────────────────────────
    async def wait_until_healthy(
        self,
        host_port: int,
        max_wait_seconds: int = 180,
        inference_host: str = "localhost",
    ) -> bool:
        """
        Poll GET http://{inference_host}:{port}/health until 200 or timeout.
        Uses exponential backoff starting at 1s, max 5s between retries.
        Returns True if healthy, False if timed out.
        """
        import httpx

        url = f"http://{inference_host}:{host_port}/health"
        wait = 1.0
        elapsed = 0.0

        async with httpx.AsyncClient() as client:
            while elapsed < max_wait_seconds:
                try:
                    resp = await client.get(url, timeout=3.0)
                    if resp.status_code == 200:
                        logger.info(f"Container healthy at {url} after {elapsed:.1f}s")
                        return True
                except httpx.RequestError:
                    pass  # Container still starting

                await asyncio.sleep(wait)
                elapsed += wait
                wait = min(wait * 1.5, 5.0)

        logger.warning(f"Container at {url} did not become healthy within {max_wait_seconds}s")
        return False


# Singleton — one DockerManager per process
_docker_manager: DockerManager | None = None


def get_docker_manager() -> DockerManager:
    global _docker_manager
    if _docker_manager is None:
        _docker_manager = DockerManager()
    return _docker_manager
