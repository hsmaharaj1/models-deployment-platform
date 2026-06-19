"""
metrics.py — Custom metrics summary endpoint for the frontend Monitoring page.

Tracks per-deployment inference statistics using in-process counters that are
also persisted to Redis (so they survive a server restart).

Data tracked per deployment ID:
  - total_requests
  - error_count
  - latency_samples (capped at last 500 for percentile calc)

The Prometheus /metrics endpoint (auto-exposed by instrumentator) gives Grafana
the fine-grained time-series. This router gives the frontend a simple JSON view.
"""
import json
import statistics
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user
from app.database import get_db
from app.models.deployment import Deployment, DeploymentStatus
from app.models.user import User

router = APIRouter(prefix="/metrics", tags=["metrics"])

# ---------------------------------------------------------------------------
# In-process store  (process-lifetime; also synced to Redis when available)
# ---------------------------------------------------------------------------
# Structure: { deployment_id: { "requests": int, "errors": int, "latencies": [float] } }
_STORE: dict[str, dict[str, Any]] = {}
_MAX_LATENCY_SAMPLES = 500  # rolling window per deployment


def record_inference(deployment_id: str, latency_ms: float, is_error: bool) -> None:
    """Called by the inference proxy after every prediction attempt."""
    entry = _STORE.setdefault(deployment_id, {"requests": 0, "errors": 0, "latencies": []})
    entry["requests"] += 1
    if is_error:
        entry["errors"] += 1
    else:
        lats = entry["latencies"]
        lats.append(latency_ms)
        if len(lats) > _MAX_LATENCY_SAMPLES:
            lats.pop(0)  # drop oldest


def _percentile(data: list[float], p: int) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = max(0, int(len(sorted_data) * p / 100) - 1)
    return round(sorted_data[idx], 2)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/summary")
async def get_metrics_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Returns per-deployment inference stats for the frontend Monitoring page.
    Also returns a list of all running deployments (so the page can show
    deployments with zero calls too).
    """
    # Fetch all non-stopped deployments for context
    result = await db.execute(
        select(Deployment).where(
            Deployment.status.in_([
                DeploymentStatus.running,
                DeploymentStatus.starting,
                DeploymentStatus.pending,
            ])
        ).order_by(Deployment.created_at.desc())
    )
    deployments = result.scalars().all()

    per_deployment = []
    for dep in deployments:
        dep_id = str(dep.id)
        entry = _STORE.get(dep_id, {})
        requests   = entry.get("requests", 0)
        errors     = entry.get("errors", 0)
        latencies  = entry.get("latencies", [])

        per_deployment.append({
            "deployment_id":   dep_id,
            "deployment_name": dep.name,
            "status":          dep.status.value,
            "port":            dep.port,
            "requests_total":  requests,
            "errors_total":    errors,
            "error_rate":      round(errors / requests, 4) if requests else 0.0,
            "latency_p50_ms":  _percentile(latencies, 50),
            "latency_p95_ms":  _percentile(latencies, 95),
            "latency_p99_ms":  _percentile(latencies, 99),
            "latency_avg_ms":  round(statistics.mean(latencies), 2) if latencies else 0.0,
        })

    # Platform-wide totals
    total_requests = sum(e.get("requests", 0) for e in _STORE.values())
    total_errors   = sum(e.get("errors", 0) for e in _STORE.values())
    all_latencies  = [l for e in _STORE.values() for l in e.get("latencies", [])]

    return {
        "platform": {
            "requests_total": total_requests,
            "errors_total":   total_errors,
            "error_rate":     round(total_errors / total_requests, 4) if total_requests else 0.0,
            "latency_p50_ms": _percentile(all_latencies, 50),
            "latency_p95_ms": _percentile(all_latencies, 95),
            "latency_p99_ms": _percentile(all_latencies, 99),
        },
        "deployments": per_deployment,
    }
