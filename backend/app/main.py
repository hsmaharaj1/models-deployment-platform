from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, projects, registry, deployments, inference
from app.routers import metrics as metrics_router
from app.routers import jobs as jobs_router
from prometheus_fastapi_instrumentator import Instrumentator

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler — runs on startup and shutdown."""
    # Startup: nothing to do here — Alembic handles migrations
    yield
    # Shutdown: close engine connections
    from app.database import engine
    await engine.dispose()


app = FastAPI(
    title="ML Deployment Platform",
    description="Production-grade MLOps platform for model versioning, deployment, and monitoring.",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(projects.router, prefix=API_PREFIX)
app.include_router(registry.router, prefix=API_PREFIX)
app.include_router(deployments.router, prefix=API_PREFIX)
app.include_router(inference.router, prefix=API_PREFIX)
app.include_router(metrics_router.router, prefix=API_PREFIX)
app.include_router(jobs_router.router, prefix=API_PREFIX)

# Expose /metrics endpoint (Prometheus scrape target)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/api/v1/health", tags=["health"])
async def health_check():
    """Platform health check — used by Docker and load balancers."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "ml-deployment-platform-api",
    }
