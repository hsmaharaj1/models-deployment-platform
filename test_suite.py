#!/usr/bin/env python3
"""
ML Platform — Comprehensive Feature Test Suite
Covers every API endpoint across Phase 1 and Phase 2.
Run with: python3 test_suite.py
Requires: backend running on localhost:8000
"""

import requests
import json
import os
import sys
import time
import tempfile
import pickle

# ── Config ────────────────────────────────────────────────────────────
BASE_URL   = "http://localhost:8000/api/v1"
ADMIN_EMAIL    = "admin@mlplatform.dev"
ADMIN_PASSWORD = "admin_secret"

# ── Colour helpers ────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

passed = failed = 0

def ok(label):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {label}")

def fail(label, detail=""):
    global failed
    failed += 1
    extra = f" → {YELLOW}{detail}{RESET}" if detail else ""
    print(f"  {RED}✗{RESET} {label}{extra}")

def section(title):
    print(f"\n{BOLD}{BLUE}{'─'*60}{RESET}")
    print(f"{BOLD}{BLUE}  {title}{RESET}")
    print(f"{BOLD}{BLUE}{'─'*60}{RESET}")

def assert_status(r, expected, label):
    if r.status_code == expected:
        ok(label)
    else:
        fail(label, f"HTTP {r.status_code} — {r.text[:120]}")

def assert_field(data, field, label, expected=None):
    if field not in data:
        fail(label, f"missing field '{field}'")
        return
    if expected is not None and data[field] != expected:
        fail(label, f"expected {expected!r}, got {data[field]!r}")
        return
    ok(label)


# ── Helpers ───────────────────────────────────────────────────────────
def get_token():
    r = requests.post(f"{BASE_URL}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]

def h(token):
    return {"Authorization": f"Bearer {token}"}

def make_sklearn_model():
    """Create a minimal sklearn pickle in a temp file."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.datasets import load_iris
        import joblib, io
        X, y = load_iris(return_X_y=True)
        clf = LogisticRegression(max_iter=200, random_state=0)
        clf.fit(X, y)
        buf = io.BytesIO()
        joblib.dump(clf, buf)
        buf.seek(0)
        return buf.read(), "logreg_iris.pkl"
    except ImportError:
        # Fallback: a raw pickle of a dict (server will reject but we test upload path)
        import pickle, io
        buf = io.BytesIO()
        pickle.dump({"dummy": True}, buf)
        buf.seek(0)
        return buf.read(), "dummy.pkl"


# ═══════════════════════════════════════════════════════════════════════
# 1. HEALTH
# ═══════════════════════════════════════════════════════════════════════
section("1 · Health Check")
r = requests.get(f"{BASE_URL}/health")
assert_status(r, 200, "GET /health returns 200")
data = r.json()
assert_field(data, "status", "response has 'status' field")
assert_field(data, "status", "status == 'ok'", expected="ok")


# ═══════════════════════════════════════════════════════════════════════
# 2. AUTH
# ═══════════════════════════════════════════════════════════════════════
section("2 · Authentication")

# 2a. Bad login
r = requests.post(f"{BASE_URL}/auth/login",
                  json={"email": "nobody@example.com", "password": "wrong"})
assert_status(r, 401, "Invalid credentials → 401")

# 2b. Good login
r = requests.post(f"{BASE_URL}/auth/login",
                  json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
assert_status(r, 200, "Valid login → 200")
assert_field(r.json(), "access_token", "Response has access_token")
assert_field(r.json(), "token_type",   "Response has token_type")
token = r.json()["access_token"]

# 2c. /me
r = requests.get(f"{BASE_URL}/auth/me", headers=h(token))
assert_status(r, 200, "GET /auth/me → 200")
me = r.json()
assert_field(me, "email", "me.email present")
assert_field(me, "id",    "me.id present")
if me.get("email") == ADMIN_EMAIL:
    ok("me.email matches admin email")
else:
    fail("me.email matches admin email", f"got {me.get('email')}")

# 2d. Unauthenticated request
r = requests.get(f"{BASE_URL}/projects")
assert_status(r, 401, "No token → 401 on protected route")

# 2e. Garbage token
r = requests.get(f"{BASE_URL}/projects", headers={"Authorization": "Bearer garbage.token.here"})
assert_status(r, 401, "Garbage token → 401")


# ═══════════════════════════════════════════════════════════════════════
# 3. PROJECTS
# ═══════════════════════════════════════════════════════════════════════
section("3 · Projects")

# 3a. Create
proj_payload = {"name": "test-project-auto", "description": "Created by test suite"}
r = requests.post(f"{BASE_URL}/projects", json=proj_payload, headers=h(token))
assert_status(r, 201, "POST /projects → 201")
proj = r.json()
project_id = proj["id"]
assert_field(proj, "id",          "project.id present")
assert_field(proj, "name",        "project.name present")
assert_field(proj, "name",        "project.name == 'test-project-auto'", expected="test-project-auto")
assert_field(proj, "model_count", "project.model_count present")

# 3b. Duplicate name
r = requests.post(f"{BASE_URL}/projects", json=proj_payload, headers=h(token))
if r.status_code in [400, 409]:
    ok("Duplicate project name → 4xx")
else:
    fail("Duplicate project name → 4xx", f"got {r.status_code}")

# 3c. List
r = requests.get(f"{BASE_URL}/projects", headers=h(token))
assert_status(r, 200, "GET /projects → 200")
projects = r.json()
if isinstance(projects, list):
    ok("Response is a list")
else:
    fail("Response is a list", f"got {type(projects)}")
ids = [p["id"] for p in projects]
if project_id in ids:
    ok("New project appears in list")
else:
    fail("New project appears in list")

# 3d. Get by ID
r = requests.get(f"{BASE_URL}/projects/{project_id}", headers=h(token))
assert_status(r, 200, "GET /projects/{id} → 200")
assert_field(r.json(), "id", "project.id matches", expected=project_id)

# 3e. Get non-existent
r = requests.get(f"{BASE_URL}/projects/00000000-0000-0000-0000-000000000000", headers=h(token))
assert_status(r, 404, "GET /projects/{fake-id} → 404")

# 3f. Missing required field
r = requests.post(f"{BASE_URL}/projects", json={"description": "no name"}, headers=h(token))
assert_status(r, 422, "Create project without name → 422")


# ═══════════════════════════════════════════════════════════════════════
# 4. MODEL REGISTRY
# ═══════════════════════════════════════════════════════════════════════
section("4 · Model Registry")

model_bytes, model_filename = make_sklearn_model()

# 4a. Upload model
files   = {"file": (model_filename, model_bytes, "application/octet-stream")}
fields  = {"version_tag": "v1.0-logreg", "framework": "sklearn",
           "description": "Logistic regression on iris — test suite"}
r = requests.post(f"{BASE_URL}/projects/{project_id}/models",
                  files=files, data=fields, headers=h(token))
assert_status(r, 201, "POST upload model → 201")
model = r.json()
model_id = model["id"]
assert_field(model, "id",                "model.id present")
assert_field(model, "version_tag",       "model.version_tag present")
assert_field(model, "framework",         "model.framework == 'sklearn'", expected="sklearn")
assert_field(model, "original_filename", "model.original_filename present")
assert_field(model, "file_size_bytes",   "model.file_size_bytes present")
assert_field(model, "status",            "model.status present")
if model.get("file_size_bytes", 0) > 0:
    ok("model.file_size_bytes > 0")
else:
    fail("model.file_size_bytes > 0", f"got {model.get('file_size_bytes')}")

# 4b. Upload wrong extension
bad_files = {"file": ("model.txt", b"not a model", "text/plain")}
bad_fields = {"version_tag": "v0.bad", "framework": "sklearn"}
r = requests.post(f"{BASE_URL}/projects/{project_id}/models",
                  files=bad_files, data=bad_fields, headers=h(token))
if r.status_code in [400, 422]:
    ok("Upload unsupported extension → 4xx")
else:
    fail("Upload unsupported extension → 4xx", f"got {r.status_code}: {r.text[:80]}")

# 4c. Upload duplicate version tag
files2  = {"file": (model_filename, model_bytes, "application/octet-stream")}
fields2 = {"version_tag": "v1.0-logreg", "framework": "sklearn"}
r = requests.post(f"{BASE_URL}/projects/{project_id}/models",
                  files=files2, data=fields2, headers=h(token))
if r.status_code in [400, 409]:
    ok("Duplicate version_tag → 4xx")
else:
    fail("Duplicate version_tag → 4xx", f"got {r.status_code}: {r.text[:80]}")

# 4d. Upload second version (for rollback test later)
files3  = {"file": (model_filename, model_bytes, "application/octet-stream")}
fields3 = {"version_tag": "v2.0-logreg", "framework": "sklearn",
           "description": "Second version for rollback test"}
r = requests.post(f"{BASE_URL}/projects/{project_id}/models",
                  files=files3, data=fields3, headers=h(token))
assert_status(r, 201, "Upload second model version → 201")
model_v2_id = r.json()["id"]

# 4e. List models
r = requests.get(f"{BASE_URL}/projects/{project_id}/models", headers=h(token))
assert_status(r, 200, "GET /projects/{id}/models → 200")
models_list = r.json()
if isinstance(models_list, list) and len(models_list) >= 2:
    ok(f"Model list has ≥ 2 entries (got {len(models_list)})")
else:
    fail("Model list has ≥ 2 entries", f"got {models_list}")

# 4f. Get model by ID
r = requests.get(f"{BASE_URL}/models/{model_id}", headers=h(token))
assert_status(r, 200, "GET /models/{id} → 200")
assert_field(r.json(), "id", "model.id matches", expected=model_id)

# 4g. Get non-existent model
r = requests.get(f"{BASE_URL}/models/00000000-0000-0000-0000-000000000000", headers=h(token))
assert_status(r, 404, "GET /models/{fake-id} → 404")

# 4h. PATCH model (update status)
r = requests.patch(f"{BASE_URL}/models/{model_id}",
                   json={"status": "deprecated"}, headers=h(token))
if r.status_code in [200, 204]:
    ok("PATCH /models/{id} (deprecate) → 2xx")
else:
    fail("PATCH /models/{id} → 2xx", f"got {r.status_code}: {r.text[:80]}")

# Restore to ready for deployment tests
requests.patch(f"{BASE_URL}/models/{model_id}", json={"status": "ready"}, headers=h(token))


# ═══════════════════════════════════════════════════════════════════════
# 5. DEPLOYMENTS (non-Docker paths)
# ═══════════════════════════════════════════════════════════════════════
section("5 · Deployment API (request-level validation)")

# 5a. Deploy non-existent model
r = requests.post(f"{BASE_URL}/deployments/models/00000000-0000-0000-0000-000000000000/deploy",
                  json={"name": "test"}, headers=h(token))
assert_status(r, 404, "Deploy non-existent model → 404")

# 5b. Missing name
r = requests.post(f"{BASE_URL}/deployments/models/{model_id}/deploy",
                  json={}, headers=h(token))
assert_status(r, 422, "Deploy without name → 422")

# 5c. Deploy with valid model → 202
r = requests.post(f"{BASE_URL}/deployments/models/{model_id}/deploy",
                  json={"name": "test-deploy-suite"}, headers=h(token))
assert_status(r, 202, "POST deploy valid model → 202")
dep = r.json()
dep_id = dep["id"]
assert_field(dep, "id",               "deployment.id present")
assert_field(dep, "status",           "deployment.status present")
assert_field(dep, "port",             "deployment.port present")
assert_field(dep, "model_version_id", "deployment.model_version_id present")
if dep.get("status") == "pending":
    ok("deployment.status == 'pending' immediately after create")
else:
    fail("deployment.status == 'pending'", f"got {dep.get('status')}")
if dep.get("port") and 9000 <= dep["port"] <= 9099:
    ok(f"deployment.port in 9000-9099 range (got {dep['port']})")
else:
    fail("deployment.port in range", f"got {dep.get('port')}")

# 5d. Deploy same model again to get a second deployment for stop test
r2 = requests.post(f"{BASE_URL}/deployments/models/{model_v2_id}/deploy",
                   json={"name": "test-deploy-suite-v2"}, headers=h(token))
assert_status(r2, 202, "Deploy second model version → 202")
dep2_id = r2.json()["id"]

# 5e. List all deployments
r = requests.get(f"{BASE_URL}/deployments", headers=h(token))
assert_status(r, 200, "GET /deployments → 200")
deps = r.json()
if isinstance(deps, list):
    ok(f"Deployment list is a list (got {len(deps)} entries)")
else:
    fail("Deployment list is a list")
dep_ids = [d["id"] for d in deps]
if dep_id in dep_ids:
    ok("New deployment appears in list")
else:
    fail("New deployment appears in list")

# 5f. model_version nested in detail response
for d in deps:
    if d["id"] == dep_id:
        if d.get("model_version") and d["model_version"].get("framework"):
            ok("Detail response includes nested model_version with framework")
        else:
            fail("Detail response includes nested model_version", str(d.get("model_version")))
        break

# 5g. Get single deployment
r = requests.get(f"{BASE_URL}/deployments/{dep_id}", headers=h(token))
assert_status(r, 200, "GET /deployments/{id} → 200")
assert_field(r.json(), "id", "deployment.id matches", expected=dep_id)

# 5h. Get non-existent deployment
r = requests.get(f"{BASE_URL}/deployments/00000000-0000-0000-0000-000000000000", headers=h(token))
assert_status(r, 404, "GET /deployments/{fake-id} → 404")

# 5i. Stop deployment (stop the 2nd one — the 1st we keep for logs/predict tests)
time.sleep(1)
r = requests.post(f"{BASE_URL}/deployments/{dep2_id}/stop", headers=h(token))
assert_status(r, 200, "POST /deployments/{id}/stop → 200")
assert_field(r.json(), "status", "stopped status == 'stopped'", expected="stopped")

# 5j. Stop an already-stopped deployment → 400
r = requests.post(f"{BASE_URL}/deployments/{dep2_id}/stop", headers=h(token))
assert_status(r, 400, "Stop already-stopped deployment → 400")

# 5k. Predict on non-running deployment → 409
r = requests.post(f"{BASE_URL}/deployments/{dep_id}/predict",
                  json={"inputs": [[5.1, 3.5, 1.4, 0.2]]}, headers=h(token))
assert_status(r, 409, "Predict on pending deployment → 409")

# 5l. Predict with wrong input shape → 422
r = requests.post(f"{BASE_URL}/deployments/{dep_id}/predict",
                  json={"inputs": "not-an-array"}, headers=h(token))
assert_status(r, 422, "Predict with invalid input → 422")

# 5m. Logs endpoint on pending deployment (no container yet)
r = requests.get(f"{BASE_URL}/deployments/{dep_id}/logs", headers=h(token))
assert_status(r, 200, "GET /deployments/{id}/logs → 200 (even if no container)")
if "logs" in r.json():
    ok("Logs response has 'logs' key")
else:
    fail("Logs response has 'logs' key")


# ═══════════════════════════════════════════════════════════════════════
# 6. RUNNING DEPLOYMENT (Docker-dependent) 
# ═══════════════════════════════════════════════════════════════════════
section("6 · Live Inference (requires Docker Desktop running)")

# Check if a running deployment exists from a prior session
r = requests.get(f"{BASE_URL}/deployments", headers=h(token))
running_deps = [d for d in r.json() if d.get("status") == "running"]

if running_deps:
    live_id = running_deps[0]["id"]
    live_url = running_deps[0]["endpoint_url"]
    print(f"  Found running deployment: {running_deps[0]['name']} @ {live_url}")

    # 6a. Predict single sample
    r = requests.post(f"{BASE_URL}/deployments/{live_id}/predict",
                      json={"inputs": [[5.1, 3.5, 1.4, 0.2]]}, headers=h(token))
    assert_status(r, 200, "Predict single iris sample → 200")
    pred = r.json()
    assert_field(pred, "predictions", "response has 'predictions'")
    assert_field(pred, "latency_ms",  "response has 'latency_ms'")
    if isinstance(pred.get("predictions"), list) and len(pred["predictions"]) == 1:
        ok(f"1 prediction returned: {pred['predictions']}")
    else:
        fail("1 prediction returned", str(pred.get("predictions")))

    # 6b. Predict batch
    batch = [[5.1, 3.5, 1.4, 0.2], [6.7, 3.0, 5.2, 2.3], [5.9, 3.0, 4.2, 1.5]]
    r = requests.post(f"{BASE_URL}/deployments/{live_id}/predict",
                      json={"inputs": batch}, headers=h(token))
    assert_status(r, 200, "Predict batch of 3 samples → 200")
    pred = r.json()
    if isinstance(pred.get("predictions"), list) and len(pred["predictions"]) == 3:
        ok(f"Batch: 3 predictions returned → {pred['predictions']}")
    else:
        fail("Batch: 3 predictions returned", str(pred.get("predictions")))
    if isinstance(pred.get("latency_ms"), float) and pred["latency_ms"] > 0:
        ok(f"latency_ms > 0 (got {pred['latency_ms']:.2f}ms)")
    else:
        fail("latency_ms > 0", str(pred.get("latency_ms")))

    # 6c. Container health directly
    port = running_deps[0]["port"]
    try:
        rh = requests.get(f"http://localhost:{port}/health", timeout=3)
        if rh.status_code == 200 and rh.json().get("status") == "healthy":
            ok(f"Direct container /health → healthy (port {port})")
        else:
            fail("Direct container /health", f"{rh.status_code} {rh.text[:50]}")
    except Exception as e:
        fail("Direct container /health reachable", str(e))

    # 6d. Logs of live container
    r = requests.get(f"{BASE_URL}/deployments/{live_id}/logs", headers=h(token))
    assert_status(r, 200, "GET logs of running deployment → 200")
    logs = r.json().get("logs", "")
    if "Application startup complete" in logs or "Model loaded" in logs:
        ok("Container logs contain startup messages")
    else:
        fail("Container logs contain startup messages", logs[:100])

    # 6e. Recover endpoint on running deployment → 400 (already running)
    r = requests.post(f"{BASE_URL}/deployments/{live_id}/recover", headers=h(token))
    assert_status(r, 400, "Recover already-running deployment → 400")

else:
    print(f"  {YELLOW}⚠ No running deployments found — skipping Docker-dependent tests.")
    print(f"    (Start Docker Desktop and deploy a model to run these tests){RESET}")


# ═══════════════════════════════════════════════════════════════════════
# 7. ROLLBACK VALIDATION
# ═══════════════════════════════════════════════════════════════════════
section("7 · Rollback Validation")

# Rollback on a stopped deployment with only 1 version → 400
# First find a deployment with no previous version
r = requests.post(f"{BASE_URL}/deployments/{dep2_id}/rollback", headers=h(token))
if r.status_code in [400, 202]:
    ok(f"Rollback on stopped deployment → {r.status_code} (expected 400 or 202)")
else:
    fail("Rollback returns valid response", f"got {r.status_code}: {r.text[:80]}")


# ═══════════════════════════════════════════════════════════════════════
# 8. CLEANUP
# ═══════════════════════════════════════════════════════════════════════
section("8 · Cleanup (delete test project)")

# Stop all non-stopped deployments in our test project before deleting
r = requests.get(f"{BASE_URL}/deployments", headers=h(token))
for d in r.json():
    if d["model_version"].get("project_id") == project_id and d["status"] not in ["stopped", "failed"]:
        requests.post(f"{BASE_URL}/deployments/{d['id']}/stop", headers=h(token))

# Delete models first
for model_to_del in [model_id, model_v2_id]:
    r = requests.delete(f"{BASE_URL}/models/{model_to_del}", headers=h(token))
    if r.status_code in [200, 204]:
        ok(f"DELETE /models/{model_to_del[:8]}... → {r.status_code}")
    else:
        fail(f"DELETE /models/{model_to_del[:8]}...", f"{r.status_code}: {r.text[:60]}")

# Delete the test project
r = requests.delete(f"{BASE_URL}/projects/{project_id}", headers=h(token))
if r.status_code in [200, 204]:
    ok("DELETE /projects/{id} → 2xx")
else:
    fail("DELETE /projects/{id}", f"{r.status_code}: {r.text[:80]}")

# Confirm project gone
r = requests.get(f"{BASE_URL}/projects/{project_id}", headers=h(token))
assert_status(r, 404, "Deleted project returns 404")


# ═══════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
total = passed + failed
print(f"{BOLD}  Results: {GREEN}{passed} passed{RESET}{BOLD}, {RED}{failed} failed{RESET}{BOLD}, {total} total{RESET}")
print(f"{'═'*60}\n")

if failed > 0:
    sys.exit(1)
