# ML Deployment Platform — Feature Reference

> **Owner:** Himanshu Sekhar · Built as a production-grade MLOps portfolio project
>
> Stack: FastAPI · PostgreSQL · Redis · Docker SDK · React + TypeScript + Vite + Tailwind CSS

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Phase 1 — Core Platform](#phase-1--core-platform)
   - [Authentication](#authentication)
   - [Projects](#projects)
   - [Model Registry](#model-registry)
   - [Frontend (Phase 1)](#frontend-phase-1)
3. [Phase 2 — Deployment Engine](#phase-2--deployment-engine)
   - [Inference Server Images](#inference-server-images)
   - [Docker Manager](#docker-manager)
   - [Deployment Service (State Machine)](#deployment-service-state-machine)
   - [Deployment API](#deployment-api)
   - [Inference Proxy](#inference-proxy)
   - [Frontend (Phase 2)](#frontend-phase-2)
4. [Data Models](#data-models)
5. [API Reference](#api-reference)
6. [Environment & Configuration](#environment--configuration)
7. [Known Behaviours & Design Decisions](#known-behaviours--design-decisions)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (localhost:5173)                  │
│              React + TypeScript + Vite + Tailwind            │
└─────────────────────────┬───────────────────────────────────┘
                           │ HTTP/REST (Axios + JWT)
┌─────────────────────────▼───────────────────────────────────┐
│              FastAPI Platform API (localhost:8000)            │
│   Auth · Projects · Registry · Deployments · Inference Proxy  │
│                   SQLAlchemy (async)                         │
└──────┬────────────────────┬──────────────────────┬──────────┘
       │                    │                       │
┌──────▼──────┐    ┌────────▼────────┐   ┌─────────▼────────┐
│ PostgreSQL  │    │      Redis      │   │   Docker Engine   │
│  port 5433  │    │   port 6379     │   │  (macOS socket)   │
│  (compose)  │    │   (compose)     │   │                   │
└─────────────┘    └─────────────────┘   └──────────┬────────┘
                                                     │
                                         ┌───────────▼─────────────────┐
                                         │  Inference Containers (per  │
                                         │  deployment, ports 9000-9099)│
                                         │  mlplatform-sklearn-server   │
                                         │  mlplatform-torch-server     │
                                         └─────────────────────────────┘
```

- **Single-user admin tool** — no multi-tenancy; all resources belong to the admin.
- **Artifact store** — model files saved on the host filesystem, mounted as **read-only** volumes into inference containers.
- **Port pool** — each deployment claims one port from `9000–9099`.

---

## Phase 1 — Core Platform

### Authentication

**Purpose:** Single-user JWT-based auth. One hard-coded admin account, seeded automatically on startup.

**Implementation files:**
- `backend/app/routers/auth.py` — HTTP endpoints
- `backend/app/core/auth.py` — JWT issue/verify, password hashing, `get_current_user` FastAPI dependency
- `backend/app/models/user.py` — SQLAlchemy `User` ORM model

**How it works:**
1. Admin credentials are read from `Settings` (env vars / `.env`).
2. On startup the seeder checks if the admin user exists in the DB; creates it if not.
3. Login hashes the password with **bcrypt** (via `passlib[bcrypt]==1.7.4`, `bcrypt==4.0.1` pinned to avoid passlib compat break in v5+).
4. A signed **JWT** is returned. Default TTL: **24 hours** (`ACCESS_TOKEN_EXPIRE_MINUTES=1440`).
5. All protected routes use `Depends(get_current_user)` which decodes the JWT and returns the `User` object.

**Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/register` | Register a new user (open) |
| `POST` | `/api/v1/auth/login` | Get JWT token |
| `GET`  | `/api/v1/auth/me` | Fetch current user info |

**Key design decisions:**
- `passlib` is used for hashing but `bcrypt` is pinned to `4.0.1` — v5 broke the `passlib` API.
- Email validation via Pydantic `EmailStr` — `.local` TLDs rejected; admin email uses `.dev` domain.
- JWT algorithm: `HS256` with a configurable secret key.

---

### Projects

**Purpose:** Top-level organizational unit — groups model versions together.

**Implementation files:**
- `backend/app/routers/projects.py`
- `backend/app/models/project.py`
- `backend/app/schemas/project.py`

**How it works:**
- A `Project` has `name`, `description`, and timestamps.
- `model_count` is a computed field (count of associated `ModelVersion` rows).
- Deleting a project cascades to its model versions and associated artifacts.
- Project names must be unique (DB-level unique constraint).

**Endpoints:**
| Method   | Path | Description |
|----------|------|-------------|
| `POST`   | `/api/v1/projects` | Create a project |
| `GET`    | `/api/v1/projects` | List all projects |
| `GET`    | `/api/v1/projects/{id}` | Get a single project |
| `PUT`    | `/api/v1/projects/{id}` | Update project metadata |
| `DELETE` | `/api/v1/projects/{id}` | Delete project + cascade |

---

### Model Registry

**Purpose:** Upload and manage versioned ML model artifacts. Each model version belongs to a project and carries its framework type, version tag, and file metadata.

**Implementation files:**
- `backend/app/routers/registry.py`
- `backend/app/models/model_version.py`
- `backend/app/core/storage.py` — filesystem artifact store
- `backend/app/schemas/model_version.py`

**How it works:**
1. Upload is a `multipart/form-data` `POST` with the binary model file + metadata fields.
2. The file is validated for extension (`.pkl`, `.joblib`, `.pt`, `.pth`) and saved under:
   ```
   artifacts/projects/{project_id}/models/{model_id}/{filename}
   ```
3. `artifact_path` (the relative path) is stored in the DB.
4. Model status lifecycle: `uploaded → ready → deprecated`
5. Duplicate `version_tag` within the same project is rejected (`409`).

**Endpoints:**
| Method   | Path | Description |
|----------|------|-------------|
| `POST`   | `/api/v1/projects/{id}/models` | Upload model file (multipart) |
| `GET`    | `/api/v1/projects/{id}/models` | List model versions for a project |
| `GET`    | `/api/v1/models/{model_id}` | Get single model version |
| `PATCH`  | `/api/v1/models/{model_id}` | Update model status/description |
| `DELETE` | `/api/v1/models/{model_id}` | Delete model record + artifact file |

**Key design decisions:**
- Artifacts are stored **on the host filesystem** (not S3/GCS) for simplicity, but the `StorageBackend` abstraction makes it easy to swap to object storage later.
- `file_size_bytes` recorded at upload time.
- File extension whitelist prevents arbitrary file execution inside inference containers.

---

### Frontend (Phase 1)

**Purpose:** Clean admin SPA with dark-themed UI for managing projects and models.

**Implementation files:**
- `frontend/src/pages/Login.tsx` — JWT login form
- `frontend/src/pages/Dashboard.tsx` — project list + create modal
- `frontend/src/pages/ProjectDetail.tsx` — model version table + upload modal
- `frontend/src/components/Layout.tsx` — sidebar nav + logout
- `frontend/src/api/client.ts` — Axios instance with JWT interceptor
- `frontend/src/api/index.ts` — typed API functions

**Key features:**
- **JWT interceptor** — auto-attaches `Authorization: Bearer {token}` header; on `401` automatically redirects to `/login` and clears token from localStorage.
- **Upload progress bar** — Axios `onUploadProgress` callback drives a real-time progress indicator.
- **File drop zone** — click-to-select with `.pkl/.joblib/.pt/.pth` filter.
- **Framework badge coloring** — sklearn = blue, pytorch = red.
- **Model table** — sortable columns, `latest` badge on newest version, hover-reveal action buttons.
- **Private route guard** — checks `localStorage.access_token`; redirects to login if missing.

---

## Phase 2 — Deployment Engine

### Inference Server Images

**Purpose:** Lightweight containerized servers that load a model file on startup and serve predictions over HTTP.

**Implementation:**

#### `mlplatform-sklearn-server:latest`
- Base: `python:3.11-slim`
- Deps: `scikit-learn`, `fastapi`, `uvicorn`
- Exposes port `8080` (mapped to host port `900x`)
- Reads `MODEL_PATH` env var to locate the artifact
- **`/health`** — returns `{"status": "healthy", "model_type": "<class_name>"}`
- **`/predict`** — accepts `{"inputs": [[...]]}` (array of arrays), returns `{"predictions": [...], "latency_ms": float}`

#### `mlplatform-torch-server:latest`
- Base: `python:3.11-slim`
- Deps: `torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu` (CPU-only, ~500MB vs 2GB CUDA)
- Same `/health` + `/predict` interface
- Loads `.pt`/`.pth` via `torch.load` with `weights_only=False`

**Build commands:**
```bash
docker build -t mlplatform-sklearn-server:latest ./inference-servers/sklearn-server/
docker build -t mlplatform-torch-server:latest   ./inference-servers/torch-server/
```

---

### Docker Manager

**Purpose:** Singleton service wrapping the Docker Python SDK — handles container lifecycle, port allocation, and health polling.

**Implementation file:** `backend/app/core/docker_manager.py`

**Key capabilities:**

#### Port allocation
```python
find_free_port(used_ports: list[int]) -> int
```
Scans `9000–9099`, returns the first port not in `used_ports`. The used port list is queried from the DB (all `pending/starting/running` deployments).

#### Container startup
```python
start_inference_container(deployment_id, framework, artifact_path, host_port) -> Container
```
- Selects Docker image by framework (`sklearn` → `mlplatform-sklearn-server:latest`)
- Resolves artifact path to absolute, computes in-container path relative to mount point
- Mounts `artifact_store_base` as `/app/artifacts` **read-only**
- Sets `MODEL_PATH` and `PORT=8080` env vars
- Runs detached, named `mlplatform-{deployment_id}`

#### Health polling
```python
wait_until_healthy(host_port, max_wait_seconds=180, inference_host="localhost") -> bool
```
- Polls `GET http://localhost:{port}/health` with exponential backoff (1s → 5s max)
- Returns `True` on first `HTTP 200`, `False` on timeout
- 180-second window to handle first-run Docker image pull overhead

#### Volume mount path resolution
The artifact store path from config may be relative (`./artifacts`). The `artifact_store_abs_path` property resolves it to absolute using `Path.resolve()` to ensure Docker volume mounts always work regardless of CWD.

---

### Deployment Service (State Machine)

**Purpose:** Business logic for the full deployment lifecycle. Separates state transitions from HTTP concerns.

**Implementation file:** `backend/app/services/deployment_service.py`

**State machine:**
```
pending ──► starting ──► running
                    └──► failed
running ──► stopped
failed  ──► stopped (via rollback)
```

#### `deploy()` — non-blocking deployment creation
1. Queries DB for used ports → picks next free port
2. Creates `Deployment` row with `status=pending`
3. Flushes (not commits) and returns immediately
4. **Router commits** before calling `add_task()` — critical to ensure the background task's fresh DB session can see the new row.

#### `start_container_background()` — background task
Runs in a new `AsyncSessionLocal()` session (cannot reuse the request session):
1. Fetch `Deployment` + `ModelVersion` from DB
2. Set status → `starting`, commit
3. Call `DockerManager.start_inference_container()` (blocking, wrapped in `asyncio.to_thread`)
4. Save `container_id`, commit
5. Call `DockerManager.wait_until_healthy()` (async polling)
6. On success: status → `running`, set `endpoint_url`, commit
7. On failure: status → `failed`, store error, attempt container cleanup

#### `stop()` — graceful stop
1. Call `DockerManager.stop_and_remove_container()` (10s timeout, then force kill)
2. Set status → `stopped`, record `stopped_at`

#### `rollback()` — version rollback
1. Query `ModelVersion.project_id` directly (no lazy relationship access)
2. Find all versions for project, sorted newest-first
3. Locate current version's index → pick `index + 1` (previous version)
4. Stop current deployment
5. Call `deploy()` for the previous version → new deployment record

---

### Deployment API

**Implementation file:** `backend/app/routers/deployments.py`

| Method | Path | Returns | Description |
|--------|------|---------|-------------|
| `POST` | `/api/v1/deployments/models/{model_id}/deploy` | `202 Deployment` | Start container async |
| `GET`  | `/api/v1/deployments` | `200 Deployment[]` | List all deployments with nested model_version |
| `GET`  | `/api/v1/deployments/{id}` | `200 Deployment` | Get single with nested model_version |
| `POST` | `/api/v1/deployments/{id}/stop` | `200 Deployment` | Stop + remove container |
| `POST` | `/api/v1/deployments/{id}/rollback` | `202 Deployment` | Stop + deploy previous version |
| `GET`  | `/api/v1/deployments/{id}/logs` | `200 {logs: str}` | Container stdout/stderr |
| `POST` | `/api/v1/deployments/{id}/predict` | `200 {predictions, latency_ms}` | Proxy to inference container |
| `POST` | `/api/v1/deployments/{id}/recover` | `200 Deployment` | Promote starting→running if healthy |

#### The `/recover` endpoint
Handles the edge case where the background health-poller timed out (e.g. first Docker pull takes >3 min). It manually GETs the container's `/health` and if `200`, updates the DB record to `running` with the correct `endpoint_url`. This is also accessible via the **Recover** button in the UI.

---

### Inference Proxy

**Implementation file:** `backend/app/routers/inference.py`

**`POST /api/v1/deployments/{id}/predict`**

1. Fetch deployment, verify `status == running`
2. Forward request to `{endpoint_url}/predict` via `httpx.AsyncClient` with 30s timeout
3. Measure **platform-side latency** (includes network roundtrip to container)
4. Return `{predictions: [...], latency_ms: float}`

Input format:
```json
{ "inputs": [[feature1, feature2, ...], ...] }
```
Output format:
```json
{ "predictions": [0, 2, 1], "latency_ms": 12.605 }
```

Error handling:
- `ConnectError` → `503` (container crashed or not reachable)
- `TimeoutException` → `504` (container took >30s)
- Non-200 from container → propagated with container's error text

---

### Frontend (Phase 2)

**Implementation files:**
- `frontend/src/pages/Deployments.tsx` — full deployments management page
- `frontend/src/pages/ProjectDetail.tsx` — updated with Deploy button + modal

#### Deployments Page (`/deployments`)

**Deployment cards** — each card shows:
- Name, framework badge, version tag
- Status badge with color coding:
  - 🟡 `pending` — waiting for container
  - 🟣 `starting` — pulsing dot, container starting
  - 🟢 `running` — green, endpoint URL shown
  - ⚫ `stopped` — grey
  - 🔴 `failed` — red
- Endpoint URL (when running)
- Port, deploy time, stop time
- Action buttons: **Test Predict**, **Rollback**, **Recover**, **Logs**, **Stop**

**Auto-polling** — while any deployment is in `pending` or `starting` state, the page polls `GET /deployments` every 3 seconds and updates cards in place.

**Predict Modal** — JSON textarea pre-filled with an example input, run button, live result display with latency.

**Logs Modal** — fetches and renders container stdout/stderr in a terminal-style dark block.

**Recover button** — appears for `starting` and `failed` deployments that have a `container_id`. Calls `/recover` to manually promote to `running`.

#### Deploy Flow (ProjectDetail → Deployments)

1. Hover over a model row → **Deploy** button appears (alongside Delete)
2. Click Deploy → modal opens with auto-filled name (`{version_tag}-deploy`)
3. Info banner explains container starts async
4. Click **Deploy** → `POST /deployments/models/{id}/deploy` → `202`
5. Frontend immediately navigates to `/deployments`
6. Deployments page auto-polls until the new card transitions to `running`

---

## Data Models

### `User`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `email` | String | Unique |
| `hashed_password` | String | bcrypt |
| `is_active` | Boolean | Default true |
| `created_at` | Timestamp | |

### `Project`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `name` | String | Unique |
| `description` | String | Nullable |
| `created_at` | Timestamp | |
| `updated_at` | Timestamp | |

### `ModelVersion`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `project_id` | UUID FK → Project | Cascade delete |
| `version_tag` | String | Unique per project |
| `framework` | Enum | `sklearn`, `pytorch` |
| `original_filename` | String | |
| `artifact_path` | String | Relative filesystem path |
| `file_size_bytes` | BigInt | Nullable |
| `description` | String | Nullable |
| `metadata_json` | JSONB | Nullable |
| `status` | Enum | `uploaded`, `ready`, `deprecated` |
| `created_at` | Timestamp | |
| `updated_at` | Timestamp | |

### `Deployment`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `model_version_id` | UUID FK → ModelVersion | |
| `name` | String | Human-readable label |
| `container_id` | String | Docker container ID (long form) |
| `endpoint_url` | String | `http://localhost:{port}` |
| `port` | Integer | 9000–9099 |
| `status` | Enum | `pending`, `starting`, `running`, `stopped`, `failed` |
| `created_at` | Timestamp | |
| `stopped_at` | Timestamp | Nullable |

### `InferenceJob` *(schema only — Phase 4)*
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `deployment_id` | UUID FK → Deployment | |
| `celery_task_id` | String | Nullable |
| `status` | Enum | `queued`, `processing`, `completed`, `failed` |
| `input_payload` | JSONB | |
| `output_payload` | JSONB | |
| `latency_ms` | Float | |
| `error_message` | String | |
| `created_at` / `completed_at` | Timestamp | |

---

## API Reference

**Base URL:** `http://localhost:8000/api/v1`
**Auth:** `Authorization: Bearer {jwt_token}` on all routes except `/auth/login` and `/auth/register`
**Docs:** `http://localhost:8000/api/docs` (Swagger UI)

### Full Route List
```
GET  /health
POST /auth/register
POST /auth/login
GET  /auth/me
POST /projects
GET  /projects
GET  /projects/{id}
PUT  /projects/{id}
DEL  /projects/{id}
POST /projects/{id}/models
GET  /projects/{id}/models
GET  /models/{model_id}
PATCH /models/{model_id}
DEL  /models/{model_id}
POST /deployments/models/{model_id}/deploy   ← 202 async
GET  /deployments
GET  /deployments/{id}
POST /deployments/{id}/stop
POST /deployments/{id}/rollback
GET  /deployments/{id}/logs
POST /deployments/{id}/predict
POST /deployments/{id}/recover
```

---

## Environment & Configuration

**File:** `backend/.env` (gitignored), example at `backend/.env.example`

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...@localhost:5433/mlplatform` | PostgreSQL async URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for future Celery |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | 24h TTL |
| `ADMIN_EMAIL` | `admin@mlplatform.dev` | Seeded admin user |
| `ADMIN_PASSWORD` | `admin_secret` | Seeded admin password |
| `ARTIFACT_STORE_PATH` | `./artifacts` | Model file storage root (resolved to absolute at runtime) |
| `INFERENCE_HOST` | `localhost` | Hostname to reach inference containers |

**Infrastructure (docker-compose):**
```bash
docker compose up -d   # Starts postgres:5433 + redis:6379
```

**Backend:**
```bash
DATABASE_URL="postgresql+asyncpg://mlplatform:mlplatform_secret@localhost:5433/mlplatform" \
ARTIFACT_STORE_PATH="$(pwd)/artifacts" \
.venv/bin/uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend && npm run dev   # http://localhost:5173
```

**Test suite:**
```bash
python3 test_suite.py
```

---

## Known Behaviours & Design Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| **Async commit before background task** | `await db.commit()` in router before `add_task()` | Background task creates a new `AsyncSessionLocal()`. Without an explicit commit, the new session sees the row as non-existent (transaction isolation). |
| **180s health timeout** | Extended from 60s → 180s | First-run Docker image pull (sklearn server ~600MB) can take 2–3 min. Subsequent starts are instant (Docker layer cache). |
| **Recover endpoint** | Manual promote of `starting/failed → running` | Safety valve for when health poller races against a slow start. Callable from UI with the **Recover** button. |
| **Read-only volume mounts** | `mode: "ro"` on artifact store | Inference containers should never write to the artifact store. Prevents accidental model corruption. |
| **Port pool 9000–9099** | 100-deployment limit | Sufficient for a single-admin tool. Deployments not in `stopped/failed` state hold their port. |
| **Lazy relationship in async SQLAlchemy** | Avoided throughout | Async SQLAlchemy raises `MissingGreenlet` if you access unloaded relationships outside an async context. All relations are either eagerly loaded (`selectinload`) or queried explicitly. |
| **bcrypt pinned to 4.0.1** | `bcrypt==4.0.1` | passlib 1.7.4 is incompatible with bcrypt ≥ 5.x which restructured its internal API. |
| **PyTorch CPU-only image** | `--index-url https://download.pytorch.org/whl/cpu` | CUDA wheels are 2GB+. CPU-only keeps the image under 500MB. |
| **Single-user mode** | No multi-tenancy | Scope constraint per project brief. All resources owned by the admin user. |
| **JSON artifact metadata** | `metadata_json: JSONB` | Flexible bag for accuracy, dataset info, hyperparameters — no fixed schema required. |

---

*Last updated: June 2026 · Phase 2 complete · Phase 3 (Monitoring) upcoming*
