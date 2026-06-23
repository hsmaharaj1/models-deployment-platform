# ML Deployment Platform

A production-grade MLOps platform for model versioning, deployment, and monitoring.

> Built by Himanshu Sekhar — pre-ServiceNow portfolio project

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React + TypeScript + Vite + Tailwind CSS |
| **Backend** | FastAPI (Python 3.11) + SQLAlchemy (async) |
| **Database** | PostgreSQL 16 |
| **Queue** | Redis 7 + Celery 5 |
| **Containers** | Docker Engine (via Docker Python SDK) + Docker Compose |
| **Monitoring** | Prometheus + Grafana |
| **Verification** | Python 3.11 + Scikit-Learn |

---

## Key Features

- **Model Registry & Versioning**: Versioned model registry with support for Scikit-Learn (`.pkl`/`.joblib`) and PyTorch (`.pt`/`.pth`) artifacts.
- **Dynamic Container Engine**: Automatically spins up, configures, logs, rolls back, and stops isolated inference containers dynamically allocating ports from `9000-9099`.
- **Sync & Async Inference**: Serves low-latency synchronous predictions through a backend-managed proxy, and routes high-volume/long-running prediction batches to background workers via Redis/Celery.
- **Robust Monitoring**: Captures live metrics (latencies, counts, error rates) per deployment, rendering them in a customized dashboard with integrated Prometheus scraping and auto-provisioned Grafana visualization.
- **Full E2E Testing**: Complete automated test suite that validates the entire platform lifecycle under concurrent workloads.

---

## Quick Start

### Prerequisites
- Docker Desktop running (and configured for local container management)
- Python 3.11 (with virtual environment configured)
- Node.js 20+

### 1. Clone and Configure
```bash
cp .env.example .env
# Edit .env if needed (default values work out of the box for local development)
```

### 2. Start Database and Queue
Start PostgreSQL and Redis services in the background:
```bash
docker compose up db redis -d
```

### 3. Run Migrations & Seed Admin
Set up the tables and create the initial administrator account:
```bash
cd backend
DATABASE_URL="postgresql+asyncpg://mlplatform:mlplatform_secret@localhost:5433/mlplatform" \
  ../.venv/bin/alembic upgrade head

DATABASE_URL="postgresql+asyncpg://mlplatform:mlplatform_secret@localhost:5433/mlplatform" \
  ../.venv/bin/python scripts/seed_admin.py
```

### 4. Build Inference Server Images
Build the base Docker images that serve Scikit-Learn and PyTorch models:
```bash
docker build -t mlplatform-sklearn-server:latest ./inference-servers/sklearn-server/
docker build -t mlplatform-torch-server:latest   ./inference-servers/torch-server/
```

### 5. Start Backend, Celery Worker, and Frontend
Run the main platform components. (For development, run them in separate terminal tabs or processes):

**FastAPI Server:**
```bash
cd backend
DATABASE_URL="postgresql+asyncpg://mlplatform:mlplatform_secret@localhost:5433/mlplatform" \
ARTIFACT_STORE_PATH="/Users/himanshu/Documents/HIMANSHU/playground/deployment-platform/backend/artifacts" \
  ../.venv/bin/uvicorn app.main:app --port 8000
```

**Celery Background Worker:**
```bash
cd backend
DATABASE_URL="postgresql+asyncpg://mlplatform:mlplatform_secret@localhost:5433/mlplatform" \
ARTIFACT_STORE_PATH="/Users/himanshu/Documents/HIMANSHU/playground/deployment-platform/backend/artifacts" \
  ../.venv/bin/celery -A app.workers.celery_app worker --loglevel=info
```

**Vite Frontend:**
```bash
cd frontend
npm run dev
```

Open your browser to: **http://localhost:5173**  
**Credentials:** `admin@mlplatform.dev` / `admin_secret`

---

## Live Monitoring Configuration

Prometheus and Grafana are configured to automatically scrape inference performance:
1. Start the monitoring services:
   ```bash
   docker compose up prometheus grafana -d
   ```
2. Open Prometheus at **http://localhost:9090** to view raw metrics.
3. Open Grafana at **http://localhost:3001** (default credentials: `admin` / `admin`) to view the pre-provisioned MLOps dashboard showing deployment status, throughput, p50/p95/p99 latencies, and error rates.

---

## Running the E2E Test Suite

We provide a comprehensive E2E validation script in the root directory that performs a clean slate wipe, trains Scikit-Learn models, deploys containers, fires loads of synchronous predictions and asynchronous Celery tasks, and asserts metric correctness.

To run the suite, make sure the backend, celery, and docker compose services are active, then execute:
```bash
python3 e2e_test.py
```

---

## Development Phases

- **Phase 1** ✅ Core Platform — Auth, Projects, Model Registry
- **Phase 2** ✅ Deployment Engine — Docker serving, port pool, container life-cycle
- **Phase 3** ✅ Monitoring — Live latency percentiles, Prometheus, Grafana dashboard
- **Phase 4** ✅ Async Inference — Redis/Celery task queue, polling modal
- **Phase 5** ✅ Comprehensive E2E Testing & Verification — Full automation suite
