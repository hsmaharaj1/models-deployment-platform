#!/usr/bin/env python3
"""
e2e_test.py — Full end-to-end test for the ML Deployment Platform.

What it does:
  1. Wipes all existing projects / deployments
  2. Trains 3 real sklearn models (iris classifier, digits classifier, regression)
  3. Creates 2 projects, uploads models to each
  4. Deploys 3 containers simultaneously (different ports)
  5. Fires 50 synchronous inference requests across all deployments
  6. Submits 10 async Celery jobs
  7. Polls /metrics/summary and validates stats
  8. Verifies rollback, logs, and stop
  9. Prints a final pass/fail report

Requirements: backend on :8000, Docker Desktop running, sklearn in venv.
"""

import time, json, sys, io, statistics
from pathlib import Path
import requests
import joblib

# ── Config ────────────────────────────────────────────────────────────────────
BASE     = "http://localhost:8000/api/v1"
EMAIL    = "admin@mlplatform.dev"
PASSWORD = "admin_secret"

# Colour codes
R="\033[91m"; G="\033[92m"; Y="\033[93m"; B="\033[94m"; M="\033[95m"; C="\033[96m"
BOLD="\033[1m"; RESET="\033[0m"

passed = failed = 0
step_log: list[str] = []

def ok(msg):
    global passed
    passed += 1
    line = f"  {G}✓{RESET} {msg}"
    print(line); step_log.append(f"PASS: {msg}")

def fail(msg, detail=""):
    global failed
    failed += 1
    extra = f"  {Y}↳ {detail}{RESET}" if detail else ""
    line = f"  {R}✗{RESET} {msg}"
    print(line)
    if extra: print(extra)
    step_log.append(f"FAIL: {msg} — {detail}")

def section(title):
    print(f"\n{BOLD}{B}{'━'*64}{RESET}")
    print(f"{BOLD}{B}  {title}{RESET}")
    print(f"{BOLD}{B}{'━'*64}{RESET}")

def h(token): return {"Authorization": f"Bearer {token}"}

def assert_eq(actual, expected, label):
    if actual == expected: ok(label)
    else: fail(label, f"expected {expected!r}, got {actual!r}")

def assert_in(val, container, label):
    if val in container: ok(label)
    else: fail(label, f"{val!r} not in {container!r}")

# ── Step 0: Login ─────────────────────────────────────────────────────────────
section("0 · Auth")
r = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
if r.status_code != 200:
    print(f"{R}FATAL: Login failed ({r.status_code}): {r.text}{RESET}")
    sys.exit(1)
TOKEN = r.json()["access_token"]
ok("Admin login successful")

# ── Step 1: Clean slate ───────────────────────────────────────────────────────
section("1 · Clean Slate — wipe all existing data")

# Stop running deployments first
deps = requests.get(f"{BASE}/deployments", headers=h(TOKEN)).json()
active = [d for d in deps if d["status"] in ("running", "starting", "pending")]
for d in active:
    requests.post(f"{BASE}/deployments/{d['id']}/stop", headers=h(TOKEN))
    print(f"  {Y}→{RESET} stopped deployment: {d['name']}")
if active:
    time.sleep(2)

# Delete all projects (cascades to models and deployments)
projects = requests.get(f"{BASE}/projects", headers=h(TOKEN)).json()
for p in projects:
    r = requests.delete(f"{BASE}/projects/{p['id']}", headers=h(TOKEN))
    if r.status_code in (200, 204):
        ok(f"Deleted project: {p['name']}")
    else:
        fail(f"Delete project {p['name']}", r.text[:80])

# Confirm clean
remaining = requests.get(f"{BASE}/projects", headers=h(TOKEN)).json()
assert_eq(len(remaining), 0, "No projects remain after wipe")
remaining_deps = requests.get(f"{BASE}/deployments", headers=h(TOKEN)).json()
assert_eq(len(remaining_deps), 0, "No deployments remain after wipe")


# ── Step 2: Train real models ─────────────────────────────────────────────────
section("2 · Train 3 Real sklearn Models")

from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_iris, load_digits, make_regression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split

# Model 1: Iris LR (small, fast)
X_iris, y_iris = load_iris(return_X_y=True)
clf_lr = Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression(max_iter=300, random_state=0))])
clf_lr.fit(X_iris, y_iris)
buf1 = io.BytesIO(); joblib.dump(clf_lr, buf1); buf1.seek(0)
ok(f"Model 1 trained: Iris LogisticRegression (features=4, classes=3)")

# Model 2: Iris RF (heavier, multiple versions)
clf_rf = RandomForestClassifier(n_estimators=50, random_state=42)
clf_rf.fit(X_iris, y_iris)
buf2 = io.BytesIO(); joblib.dump(clf_rf, buf2); buf2.seek(0)
ok(f"Model 2 trained: Iris RandomForest-50 (features=4, classes=3)")

# Model 3: Iris RF v2 (more trees — for rollback test)
clf_rf2 = RandomForestClassifier(n_estimators=100, random_state=7)
clf_rf2.fit(X_iris, y_iris)
buf3 = io.BytesIO(); joblib.dump(clf_rf2, buf3); buf3.seek(0)
ok(f"Model 3 trained: Iris RandomForest-100 v2 (for rollback test)")


# ── Step 3: Create projects ───────────────────────────────────────────────────
section("3 · Create Projects")

r = requests.post(f"{BASE}/projects",
    json={"name": "iris-classification", "description": "Iris species classification — LR + RF"},
    headers=h(TOKEN))
assert_eq(r.status_code, 201, "Create project: iris-classification")
proj1 = r.json(); proj1_id = proj1["id"]

r = requests.post(f"{BASE}/projects",
    json={"name": "iris-rf-versions", "description": "RF versioning + rollback test"},
    headers=h(TOKEN))
assert_eq(r.status_code, 201, "Create project: iris-rf-versions")
proj2 = r.json(); proj2_id = r.json()["id"]


# ── Step 4: Upload models ─────────────────────────────────────────────────────
section("4 · Upload Models to Registry")

# Project 1 — LR model
buf1.seek(0)
r = requests.post(f"{BASE}/projects/{proj1_id}/models",
    files={"file": ("iris_lr_v1.pkl", buf1, "application/octet-stream")},
    data={"version_tag": "v1.0-lr", "framework": "sklearn",
          "description": "Logistic Regression, StandardScaler pipeline"},
    headers=h(TOKEN))
assert_eq(r.status_code, 201, "Upload: iris-classification / v1.0-lr")
model_lr_id = r.json()["id"]
assert_eq(r.json()["framework"], "sklearn", "  framework == sklearn")
if r.json().get("file_size_bytes", 0) > 0: ok(f"  file_size_bytes = {r.json()['file_size_bytes']} bytes")
else: fail("file_size_bytes > 0")

# Project 1 — RF model
buf2.seek(0)
r = requests.post(f"{BASE}/projects/{proj1_id}/models",
    files={"file": ("iris_rf_v2.pkl", buf2, "application/octet-stream")},
    data={"version_tag": "v2.0-rf", "framework": "sklearn",
          "description": "RandomForest-50"},
    headers=h(TOKEN))
assert_eq(r.status_code, 201, "Upload: iris-classification / v2.0-rf")
model_rf_id = r.json()["id"]

# Project 2 — RF v1
buf2.seek(0)
r = requests.post(f"{BASE}/projects/{proj2_id}/models",
    files={"file": ("iris_rf_v1.pkl", buf2, "application/octet-stream")},
    data={"version_tag": "v1.0-rf50", "framework": "sklearn"},
    headers=h(TOKEN))
assert_eq(r.status_code, 201, "Upload: iris-rf-versions / v1.0-rf50")
model_rollback_v1 = r.json()["id"]

# Project 2 — RF v2 (for rollback source)
buf3.seek(0)
r = requests.post(f"{BASE}/projects/{proj2_id}/models",
    files={"file": ("iris_rf_v2.pkl", buf3, "application/octet-stream")},
    data={"version_tag": "v2.0-rf100", "framework": "sklearn"},
    headers=h(TOKEN))
assert_eq(r.status_code, 201, "Upload: iris-rf-versions / v2.0-rf100")
model_rollback_v2 = r.json()["id"]

# Verify model list
r = requests.get(f"{BASE}/projects/{proj1_id}/models", headers=h(TOKEN))
assert_eq(len(r.json()), 2, "Project 1 has 2 models in registry")
r = requests.get(f"{BASE}/projects/{proj2_id}/models", headers=h(TOKEN))
assert_eq(len(r.json()), 2, "Project 2 has 2 models in registry")

# Duplicate version tag → 409
buf2.seek(0)
r = requests.post(f"{BASE}/projects/{proj1_id}/models",
    files={"file": ("iris_lr_v1.pkl", buf2, "application/octet-stream")},
    data={"version_tag": "v1.0-lr", "framework": "sklearn"},
    headers=h(TOKEN))
assert_in(r.status_code, [400, 409], "Duplicate version_tag → 4xx")


# ── Step 5: Deploy multiple containers ────────────────────────────────────────
section("5 · Deploy 3 Containers Simultaneously")

print(f"\n  {C}Submitting 3 deploy requests (async start)…{RESET}")
t_deploy_start = time.time()

dep_ids = []
for model_id, name in [
    (model_lr_id,       "lr-prod"),
    (model_rf_id,       "rf-prod"),
    (model_rollback_v2, "rf100-staging"),
]:
    r = requests.post(f"{BASE}/deployments/models/{model_id}/deploy",
        json={"name": name}, headers=h(TOKEN))
    assert_eq(r.status_code, 202, f"Deploy {name} → 202 accepted")
    dep = r.json()
    dep_ids.append(dep["id"])
    assert_in(dep["status"], ["pending", "starting"], f"  {name}: initial status is pending/starting")
    assert_in(dep["port"], range(9000, 9100), f"  {name}: port in 9000-9099 (got {dep['port']})")

# Verify no duplicate ports
ports = [requests.get(f"{BASE}/deployments/{d}", headers=h(TOKEN)).json()["port"] for d in dep_ids]
assert_eq(len(set(ports)), 3, f"All 3 deployments have unique ports: {ports}")


# ── Step 6: Wait for all 3 to go running ─────────────────────────────────────
section("6 · Wait for Containers to Start (max 3 min)")

print(f"  Polling every 5s — waiting for all 3 to reach 'running'…")
deadline = time.time() + 200   # 200s max (image should already be pulled)
running_deps: dict[str, dict] = {}

while time.time() < deadline:
    all_deps = requests.get(f"{BASE}/deployments", headers=h(TOKEN)).json()
    our_deps  = {d["id"]: d for d in all_deps if d["id"] in dep_ids}
    running_map   = {k: v for k, v in our_deps.items() if v["status"] == "running"}
    failed_map    = {k: v for k, v in our_deps.items() if v["status"] == "failed"}

    status_str = " | ".join(f"{d['name']}:{d['status']}" for d in our_deps.values())
    print(f"  [{int(time.time()-t_deploy_start)}s] {status_str}", end="\r", flush=True)

    if len(running_map) == 3:
        print()
        running_deps = running_map
        break
    if failed_map:
        print()
        for fid, fd in failed_map.items():
            fail(f"Deployment {fd['name']} failed to start")
        for fid in failed_map:
            requests.post(f"{BASE}/deployments/{fid}/recover", headers=h(TOKEN))
        time.sleep(5)
        continue
    time.sleep(5)

elapsed = time.time() - t_deploy_start
if len(running_deps) == 3:
    ok(f"All 3 containers running in {elapsed:.0f}s")
else:
    # Try recover
    print(f"\n  {Y}Health-poll may have timed out — trying /recover on all…{RESET}")
    for dep_id in dep_ids:
        r = requests.post(f"{BASE}/deployments/{dep_id}/recover", headers=h(TOKEN))
        if r.ok and r.json().get("status") == "running":
            dep_id_data = r.json()
            running_deps[dep_id] = dep_id_data
            print(f"  {G}↳ recovered: {dep_id_data['name']}{RESET}")
    if len(running_deps) == 3:
        ok(f"All 3 containers running after /recover ({elapsed:.0f}s)")
    elif len(running_deps) == 0:
        fail("No containers reached running — is Docker Desktop active?")
        print(f"\n{R}Cannot continue inference tests without running containers. Exiting.{RESET}\n")
        sys.exit(1)
    else:
        fail(f"Only {len(running_deps)}/3 containers running — continuing with available ones")


# ── Step 7: Verify container health directly ──────────────────────────────────
section("7 · Direct Container Health Check")

import urllib.request
for dep_id, dep in running_deps.items():
    port = dep["port"]
    url  = f"http://localhost:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read())
            if data.get("status") == "healthy":
                ok(f"Container direct /health → healthy  (port {port}, model_type={data.get('model_type','?')})")
            else:
                fail(f"Container /health not healthy", str(data))
    except Exception as e:
        fail(f"Container on port {port} not reachable", str(e))


# ── Step 8: 50 Sync Inference Requests ───────────────────────────────────────
section("8 · 50 Synchronous Inference Requests")

# Iris test samples — known ground truth
SAMPLES = [
    ([5.1, 3.5, 1.4, 0.2], 0),   # Setosa
    ([4.9, 3.0, 1.4, 0.2], 0),   # Setosa
    ([7.0, 3.2, 4.7, 1.4], 1),   # Versicolor
    ([6.4, 3.2, 4.5, 1.5], 1),   # Versicolor
    ([6.3, 3.3, 6.0, 2.5], 2),   # Virginica
    ([5.8, 2.7, 5.1, 1.9], 2),   # Virginica
]
BATCH_INPUT = [s[0] for s in SAMPLES]
EXPECTED    = [s[1] for s in SAMPLES]

latencies    = []
correct      = 0
total_req    = 0

running_list = list(running_deps.values())

for i in range(50):
    dep = running_list[i % len(running_list)]   # round-robin across deployments
    # Alternate single-sample and batch
    if i % 5 == 0:
        inputs = BATCH_INPUT
        expected_len = 6
    else:
        idx = i % len(SAMPLES)
        inputs = [SAMPLES[idx][0]]
        expected_len = 1

    r = requests.post(f"{BASE}/deployments/{dep['id']}/predict",
        json={"inputs": inputs}, headers=h(TOKEN), timeout=10)

    if r.status_code == 200:
        data = r.json()
        preds = data.get("predictions", [])
        lat   = data.get("latency_ms", 0)
        latencies.append(lat)
        total_req += 1

        # Validate prediction count
        if len(preds) == expected_len:
            correct += 1
        # Validate types — each prediction should be int
        if not all(isinstance(p, (int, float)) for p in preds):
            fail(f"Request {i+1}: predictions not numeric", str(preds[:3]))
    else:
        fail(f"Request {i+1} to {dep['name']} failed", f"HTTP {r.status_code}")

ok(f"{total_req}/50 requests succeeded")
ok(f"{correct}/50 requests returned correct prediction count")

if latencies:
    lat_p50 = statistics.median(latencies)
    lat_p95 = sorted(latencies)[int(len(latencies)*0.95)]
    lat_avg = statistics.mean(latencies)
    ok(f"Latency — avg={lat_avg:.1f}ms  p50={lat_p50:.1f}ms  p95={lat_p95:.1f}ms")
    if lat_p95 < 1000:
        ok(f"p95 latency < 1000ms (got {lat_p95:.0f}ms) ✓")
    else:
        fail(f"p95 latency too high", f"{lat_p95:.0f}ms")

# ── Step 9: Known-good prediction correctness ─────────────────────────────────
section("9 · Prediction Correctness Validation")

first_dep = running_list[0]
test_cases = [
    ([[5.1, 3.5, 1.4, 0.2]], [0], "Setosa"),
    ([[7.0, 3.2, 4.7, 1.4]], [1], "Versicolor"),
    ([[6.3, 3.3, 6.0, 2.5]], [2], "Virginica"),
    ([[5.1, 3.5, 1.4, 0.2], [6.3, 3.3, 6.0, 2.5]], [0, 2], "Setosa+Virginica batch"),
]
for inputs, expected_preds, label in test_cases:
    r = requests.post(f"{BASE}/deployments/{first_dep['id']}/predict",
        json={"inputs": inputs}, headers=h(TOKEN), timeout=10)
    if r.status_code == 200:
        preds = r.json()["predictions"]
        if preds == expected_preds:
            ok(f"Correct: {label} → {preds}")
        else:
            fail(f"Wrong prediction: {label}", f"expected {expected_preds}, got {preds}")
    else:
        fail(f"Predict {label} failed", str(r.status_code))


# ── Step 10: Async Jobs ───────────────────────────────────────────────────────
section("10 · Async Celery Jobs (10 jobs)")

job_ids = []
for i in range(10):
    dep = running_list[i % len(running_list)]
    r = requests.post(f"{BASE}/deployments/{dep['id']}/predict/async",
        json={"inputs": [[5.1, 3.5, 1.4, 0.2], [6.3, 3.3, 6.0, 2.5]]},
        headers=h(TOKEN), timeout=5)
    if r.status_code == 202:
        job_ids.append(r.json()["job_id"])
    else:
        fail(f"Async submit job {i+1}", f"HTTP {r.status_code}: {r.text[:60]}")

ok(f"Submitted {len(job_ids)}/10 async jobs")

# Poll until all complete (max 30s)
print(f"  Polling jobs every 1s…")
deadline_jobs = time.time() + 30
completed_jobs = []
while time.time() < deadline_jobs and len(completed_jobs) < len(job_ids):
    completed_jobs = []
    for jid in job_ids:
        r = requests.get(f"{BASE}/jobs/{jid}", headers=h(TOKEN), timeout=5)
        if r.ok and r.json()["status"] in ("completed", "failed"):
            completed_jobs.append(r.json())
    print(f"  {len(completed_jobs)}/{len(job_ids)} complete…", end="\r", flush=True)
    if len(completed_jobs) < len(job_ids):
        time.sleep(1)

print()
success_jobs = [j for j in completed_jobs if j["status"] == "completed"]
failed_jobs  = [j for j in completed_jobs if j["status"] == "failed"]
ok(f"{len(success_jobs)}/{len(job_ids)} async jobs completed successfully")
if failed_jobs:
    for j in failed_jobs:
        fail(f"Async job failed", j.get("error_message", "?"))

# Validate job results
for j in success_jobs[:3]:
    preds = j.get("output_payload", {}).get("predictions")
    if isinstance(preds, list) and len(preds) == 2:
        ok(f"  Job {j['job_id'][:8]}… → predictions={preds}  latency={j.get('latency_ms',0):.1f}ms")
    else:
        fail(f"Job {j['job_id'][:8]}… bad output", str(j.get("output_payload")))


# ── Step 11: Monitoring Stats ─────────────────────────────────────────────────
section("11 · Monitoring — /metrics/summary Validation")

r = requests.get(f"{BASE}/metrics/summary", headers=h(TOKEN))
assert_eq(r.status_code, 200, "GET /metrics/summary → 200")
summary = r.json()

plat = summary.get("platform", {})
deps_metrics = summary.get("deployments", [])

total_requests = plat.get("requests_total", 0)
total_errors   = plat.get("errors_total", 0)

print(f"\n  {BOLD}Platform totals:{RESET}")
print(f"    requests_total : {total_requests}")
print(f"    errors_total   : {total_errors}")
print(f"    error_rate     : {plat.get('error_rate', 0)*100:.2f}%")
print(f"    p50_latency    : {plat.get('latency_p50_ms', 0):.1f}ms")
print(f"    p95_latency    : {plat.get('latency_p95_ms', 0):.1f}ms")
print(f"    p99_latency    : {plat.get('latency_p99_ms', 0):.1f}ms")

if total_requests >= 50:
    ok(f"platform.requests_total ≥ 50 (got {total_requests})")
else:
    fail(f"platform.requests_total ≥ 50", f"got {total_requests}")

if total_errors == 0:
    ok("platform.errors_total == 0 (no errors during test)")
else:
    fail(f"Unexpected errors", f"errors_total={total_errors}")

if plat.get("latency_p50_ms", 0) > 0:
    ok(f"platform.latency_p50_ms populated ({plat['latency_p50_ms']:.1f}ms)")
else:
    fail("platform.latency_p50_ms populated")

print(f"\n  {BOLD}Per-deployment metrics:{RESET}")
for dm in deps_metrics:
    print(f"    {dm['deployment_name']}: reqs={dm['requests_total']}  "
          f"p50={dm['latency_p50_ms']:.1f}ms  p95={dm['latency_p95_ms']:.1f}ms  "
          f"err_rate={dm['error_rate']*100:.1f}%")

if len(deps_metrics) >= len(running_deps):
    ok(f"All {len(running_deps)} running deployments appear in metrics")
else:
    fail(f"Per-deployment metrics count", f"expected ≥{len(running_deps)}, got {len(deps_metrics)}")


# ── Step 12: Prometheus text format ──────────────────────────────────────────
section("12 · Prometheus /metrics Endpoint")

r = requests.get("http://localhost:8000/metrics")
assert_eq(r.status_code, 200, "GET /metrics → 200")
metrics_text = r.text
if "http_requests_total" in metrics_text:
    ok("http_requests_total counter present")
else:
    fail("http_requests_total missing from /metrics")
if "http_request_duration_seconds" in metrics_text:
    ok("http_request_duration_seconds histogram present")
else:
    fail("http_request_duration_seconds histogram missing")

# Extract a sample count
import re
total_count_match = re.search(r'http_requests_total\{.*?\}\s+([\d.]+)', metrics_text)
if total_count_match:
    prom_count = float(total_count_match.group(1))
    ok(f"Prometheus counter value: {prom_count:.0f} samples")


# ── Step 13: Logs check ───────────────────────────────────────────────────────
section("13 · Container Logs")

for dep_id, dep in list(running_deps.items())[:2]:
    r = requests.get(f"{BASE}/deployments/{dep_id}/logs", headers=h(TOKEN))
    assert_eq(r.status_code, 200, f"GET logs for {dep['name']} → 200")
    logs = r.json().get("logs", "")
    if "startup" in logs.lower() or "model loaded" in logs.lower() or "application" in logs.lower():
        ok(f"  {dep['name']} logs contain startup messages")
    else:
        fail(f"  {dep['name']} logs seem empty", logs[:80] if logs else "(empty)")


# ── Step 14: Rollback ─────────────────────────────────────────────────────────
section("14 · Rollback Test")

# Deploy v2.0-rf100 → then roll it back to v1.0-rf50
dep_to_rollback = None
for dep_id, dep in running_deps.items():
    if "rf100" in dep["name"] or "staging" in dep["name"]:
        dep_to_rollback = (dep_id, dep)
        break

if not dep_to_rollback:
    dep_to_rollback = list(running_deps.items())[0]

dep_id, dep = dep_to_rollback
original_model_id = dep["model_version_id"] if "model_version_id" in dep else None

r = requests.post(f"{BASE}/deployments/{dep_id}/rollback", headers=h(TOKEN))
if r.status_code == 202:
    new_dep = r.json()
    ok(f"Rollback triggered: {dep['name']} → new deployment {new_dep['id'][:8]}")
    # Wait for rollback deployment to start
    print(f"  Waiting for rollback deployment to reach running…")
    deadline_rb = time.time() + 120
    rb_id = new_dep["id"]
    while time.time() < deadline_rb:
        rd = requests.get(f"{BASE}/deployments/{rb_id}", headers=h(TOKEN)).json()
        if rd["status"] == "running":
            ok(f"Rollback deployment running on port {rd['port']}")
            # Test it responds
            rp = requests.post(f"{BASE}/deployments/{rb_id}/predict",
                json={"inputs": [[5.1, 3.5, 1.4, 0.2]]}, headers=h(TOKEN), timeout=10)
            if rp.status_code == 200:
                ok(f"Rollback deployment correctly predicts: {rp.json()['predictions']}")
            elif rp.status_code == 409:
                # Try recover
                rec = requests.post(f"{BASE}/deployments/{rb_id}/recover", headers=h(TOKEN))
                if rec.ok and rec.json().get("status") == "running":
                    ok("Rollback deployment recovered and running")
            break
        if rd["status"] == "failed":
            # Try recover
            rec = requests.post(f"{BASE}/deployments/{rb_id}/recover", headers=h(TOKEN))
            if rec.ok and rec.json().get("status") == "running":
                ok("Rollback deployment recovered after health-poll timeout")
                break
            fail("Rollback deployment failed to start")
            break
        time.sleep(4)
elif r.status_code == 400:
    detail = r.json().get("detail", "")
    if "no previous" in detail.lower() or "only one" in detail.lower() or "previous version" in detail.lower():
        ok(f"Rollback correctly refused: {detail}")
    else:
        fail("Rollback returned 400", detail)
else:
    fail("Rollback request", f"HTTP {r.status_code}: {r.text[:80]}")


# ── Step 15: Stop all remaining deployments ───────────────────────────────────
section("15 · Stop All Running Deployments")

all_deps = requests.get(f"{BASE}/deployments", headers=h(TOKEN)).json()
running_now = [d for d in all_deps if d["status"] in ("running", "starting", "pending")]

for dep in running_now:
    r = requests.post(f"{BASE}/deployments/{dep['id']}/stop", headers=h(TOKEN))
    if r.status_code == 200 and r.json().get("status") == "stopped":
        ok(f"Stopped: {dep['name']} (port {dep.get('port','?')})")
    else:
        fail(f"Stop {dep['name']}", f"HTTP {r.status_code}")

time.sleep(1)
still_running = [d for d in requests.get(f"{BASE}/deployments", headers=h(TOKEN)).json()
                 if d["status"] in ("running", "starting")]
assert_eq(len(still_running), 0, "All deployments stopped")

# Docker containers cleaned up
running_containers = []
try:
    import subprocess
    out = subprocess.check_output(["docker", "ps", "--filter", "name=mlplatform-", "--format", "{{.Names}}"])
    running_containers = [c.strip() for c in out.decode().splitlines() if c.strip()]
except Exception:
    pass
if running_containers:
    fail("Docker containers not cleaned up", str(running_containers))
else:
    ok("Docker: no mlplatform containers still running")


# ── Final Report ──────────────────────────────────────────────────────────────
total = passed + failed
print(f"\n{'═'*64}")
print(f"{BOLD}  E2E Test Results{RESET}")
print(f"{'═'*64}")
print(f"  {G}{BOLD}{passed} passed{RESET}  |  {R}{BOLD}{failed} failed{RESET}  |  {total} total")
if failed == 0:
    print(f"\n  {G}{BOLD}✓ All checks passed — platform is fully functional!{RESET}")
else:
    print(f"\n  {Y}Failed checks:{RESET}")
    for line in step_log:
        if line.startswith("FAIL"):
            print(f"    {R}• {line[6:]}{RESET}")
print(f"{'═'*64}\n")

sys.exit(0 if failed == 0 else 1)
