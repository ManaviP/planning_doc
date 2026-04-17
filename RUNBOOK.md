# Step-by-step guide: run Compute Allocator from a clean checkout
# =================================================================
#
# Prerequisites on your machine:
#   - Python 3.11+
#   - Node.js 20+
#   - Docker + Docker Compose (for containerised startup)
#   - minikube (for Kubernetes deployment)
#
# ─────────────────────────────────────────────────────────────────
# 1. SUPABASE PROJECT SETUP
# ─────────────────────────────────────────────────────────────────
#
# a. Create a free project at https://supabase.com
#
# b. Open the SQL editor and run the following statements:
#
#    create table workloads (
#      workload_id   text primary key,
#      name          text not null,
#      container_image text not null,
#      cpu_cores     float8 not null,
#      gpu_units     float8,
#      memory_gb     float8 not null,
#      latency_sla_ms int not null,
#      failure_prob_sla float8 not null,
#      risk_tolerance text not null,
#      budget_usd    float8,
#      energy_preference text not null,
#      priority      int not null,
#      submitted_at  timestamptz not null,
#      status        text not null default 'pending'
#    );
#
#    create table deployment_scenarios (
#      scenario_id           text primary key,
#      workload_id           text references workloads(workload_id),
#      target_node           text not null,
#      predicted_latency_ms  float8,
#      predicted_failure_prob float8,
#      estimated_cost_usd    float8,
#      estimated_energy_kwh  float8
#    );
#
#    create table agent_scores (
#      id          bigserial primary key,
#      scenario_id text references deployment_scenarios(scenario_id),
#      workload_id text references workloads(workload_id),
#      agent_name  text not null,
#      raw_score   float8 not null,
#      reasoning   text
#    );
#
#    create table decision_results (
#      workload_id          text primary key references workloads(workload_id),
#      selected_scenario_id text references deployment_scenarios(scenario_id),
#      final_scores         jsonb,
#      decision_reasoning   text,
#      decided_at           timestamptz,
#      weight_overrides     jsonb
#    );
#
#    create table log_entries (
#      id          bigserial primary key,
#      workload_id text references workloads(workload_id),
#      message     text not null,
#      level       text not null default 'info',
#      created_at  timestamptz default now()
#    );
#
#    create table node_metrics_snapshots (
#      id               bigserial primary key,
#      node_name        text not null,
#      cpu_usage_pct    float8,
#      memory_usage_pct float8,
#      gpu_usage_pct    float8,
#      pod_count        int,
#      available        boolean default true,
#      collected_at     timestamptz default now()
#    );
#
# c. Enable Realtime for all six tables:
#    Dashboard → Database → Replication → toggle each table on
#
# d. Copy your "Project URL" and "service_role key" from
#    Project Settings → API.
#
# ─────────────────────────────────────────────────────────────────
# 2. ENVIRONMENT FILES
# ─────────────────────────────────────────────────────────────────
#
# Create backend/.env:
#   SUPABASE_URL=https://<project-ref>.supabase.co
#   SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
#   PROMETHEUS_URL=http://localhost:9090
#   # Optional demo scaling when Prometheus is unavailable:
#   SYNTHETIC_NODE_COUNT=5
#
# Create frontend/.env.local:
#   VITE_SUPABASE_URL=https://<project-ref>.supabase.co
#   VITE_SUPABASE_ANON_KEY=<anon-key>
#   VITE_API_BASE_URL=http://localhost:8000
#
# ─────────────────────────────────────────────────────────────────
# 3. MINIKUBE STARTUP
# ─────────────────────────────────────────────────────────────────
#
#   minikube start --nodes 3 --cpus 2 --memory 2200 \
#     --driver docker --kubernetes-version=v1.28.3
#
#   # Install kube-prometheus-stack (Prometheus + metrics-server)
#   helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
#   helm repo update
#   kubectl create ns monitoring
#   helm install prometheus-stack prometheus-community/kube-prometheus-stack \
#     --namespace monitoring --wait
#
#   # Create workloads namespace
#   kubectl create ns workloads
#
# ─────────────────────────────────────────────────────────────────
# 4a. OPTION A — DOCKER COMPOSE (recommended)
# ─────────────────────────────────────────────────────────────────
#
#   chmod +x start.sh
#   ./start.sh
#
#   This script verifies minikube, port-forwards Prometheus on :9090,
#   then starts docker compose which boots the backend on :8000 and
#   the frontend on :3000.
#
# ─────────────────────────────────────────────────────────────────
# 4b. OPTION B — NATIVE (without Docker)
# ─────────────────────────────────────────────────────────────────
#
#   # Terminal 1 — Prometheus port-forward
#   kubectl port-forward -n monitoring svc/prometheus-stack-kube-prom-prometheus 9090:9090
#
#   # Terminal 2 — backend
#   cd "<repo-root>"
#   python -m venv .venv
#   .venv\Scripts\activate        # Windows
#   # source .venv/bin/activate   # macOS / Linux
#   pip install -r backend/requirements.txt
#   uvicorn backend.main:app --reload --port 8000
#
#   # Terminal 3 — frontend
#   cd frontend
#   npm install
#   npm run dev
#
# ─────────────────────────────────────────────────────────────────
# 5. VERIFY
# ─────────────────────────────────────────────────────────────────
#
#   curl http://localhost:8000/health         # {"status":"ok"}
#   # Browser: http://localhost:3000
#
# ─────────────────────────────────────────────────────────────────
# 6. SMOKE TEST
# ─────────────────────────────────────────────────────────────────
#
#   python test_smoke.py
#
#   Expected output:
#     Submitted workload: <uuid>
#     Workload <uuid> status: evaluating
#     Workload <uuid> status: deployed
#     Last 5 log entries:
#       - [<ts>] INFO: Pod ...: Running
#       ...
#     Decision summary:
#       Selected scenario: <scenario-uuid>
#       Selected node: minikube-m0X
#       Selected score: 82.14
#       All final scores: {...}
#
# ─────────────────────────────────────────────────────────────────
# 7. NEW CAPABILITIES (MERGED)
# ─────────────────────────────────────────────────────────────────
#
# a) YAML workload APIs
#
#    POST /workloads/yaml
#    Body:
#    {
#      "yaml_spec": "name: demo\ncontainer_image: nginx:stable\ncpu_cores: 0.5\n..."
#    }
#
#    POST /simulate/competition/yaml
#    Body:
#    {
#      "yaml_spec": "workload_a:\n  ...\nworkload_b:\n  ..."
#    }
#
# b) Audit chain APIs (tamper-evident)
#
#    GET /results/{workload_id}/audit
#    GET /results/{workload_id}/audit/verify
#
# c) Schema update for audit events
#
#    Run schema.sql in Supabase SQL editor to create:
#      - audit_events table
#      - supporting indexes
#
#    This does NOT remove or alter your existing tables; it only adds missing
#    objects with IF NOT EXISTS guards.

# ─────────────────────────────────────────────────────────────────
# 8. FREE-ONLY PREVIEW CONTROL PLANE (PHASED UPGRADE)
# ─────────────────────────────────────────────────────────────────
#
# This repository now includes a phased implementation path for the
# "AI control plane for pre-deployment decisions" idea while keeping
# the current stack and base architecture.
#
# PHASE 1 (DELIVERED): Free-only decision preview APIs
#   - POST /preview/run
#   - GET  /preview/{run_id}
#   - GET  /preview/{run_id}/export
#
# Inputs (preview/run):
#   {
#     "name": "my-workload",
#     "cpu_cores": 2,
#     "memory_gb": 4,
#     "priority": 3,
#     "policy": {
#       "max_monthly_budget_usd": 500,
#       "max_failure_probability": 0.15,
#       "max_latency_ms": 200,
#       "allowed_clouds": ["aws", "azure", "gcp"],
#       "allowed_regions": ["eu-west-1", "westeurope", "europe-west4"]
#     },
#     "weights": {"cost": 0.3, "risk": 0.35, "latency": 0.25, "energy": 0.1}
#   }
#
# Output includes:
#   - ranked options across clouds
#   - winner recommendation
#   - confidence intervals (latency/failure)
#   - guardrail pass/fail and violations
#   - free-source pricing metadata (source + fetched time)
#
# Export endpoint returns a downloadable ZIP bundle containing:
#   - deployment.yaml
#   - main.tf
#   - deploy.yml
#
# Free pricing source policy (no credit card required):
#   - Azure Retail Prices public API
#   - AWS public offer file endpoint
#   - GCP public snapshot fallback
#
# PHASE 2 (DELIVERED - baseline APIs):
#   - POST /shadow/register
#   - POST /shadow/{shadow_id}/actuals
#   - GET  /shadow/{shadow_id}
#   - GET  /shadow/trust/summary
#
# Example flow:
#   1) Register predicted outcome from preview winner
#   2) Attach actual observed cost/latency/failure
#   3) Read trust summary across compared runs
#
# PHASE 3 (DELIVERED - frontend control plane UI):
#   - Route: /preview
#   - Sidebar nav: Preview
#   - Confidence panel for winner (latency/failure intervals)
#   - Editable policy guardrails (budget/risk/latency/cloud/region)
#   - Editable scoring weights (cost/risk/latency/energy)
#   - Ranked allowed options + blocked-by-policy breakdown
#   - Shadow actuals attachment form + trust summary view
#
# PHASE 4 (DELIVERED - baseline):
#   - One-click template export from UI via /preview/{run_id}/export
#   - Frontend handoff to preview from workload + decision pages
#   - Free pricing adapters remain no-credit-card (Azure/AWS public + GCP snapshot fallback)

# ─────────────────────────────────────────────────────────────────
# 9. ONE-CLICK OPERATIONS (NEW)
# ─────────────────────────────────────────────────────────────────
#
# Local one-click startup
#   1) Copy templates:
#      - cp backend/.env.example backend/.env
#      - cp frontend/.env.local.example frontend/.env.local
#   2) Fill real Supabase keys in backend/.env and frontend/.env.local
#   3) Run:
#      Linux/macOS: make up
#      Windows:     deploy.bat up
#
# Useful one-command operations
#   Linux/macOS (Makefile):
#     - make help   (list commands)
#     - make up     (preflight checks + start stack)
#     - make down   (stop stack)
#     - make smoke  (run test_smoke.py)
#     - make gates  (run promotion gates locally)
#     - make clean  (remove stack volumes + delete minikube)
#
#   Windows (batch script):
#     - deploy.bat help   (list commands)
#     - deploy.bat up     (preflight checks + start stack)
#     - deploy.bat down   (stop docker compose)
#     - deploy.bat smoke  (run test_smoke.py)
#     - deploy.bat gates  (run promotion gates locally)
#     - deploy.bat clean  (remove volumes + delete minikube)
#
# start.sh preflight now verifies:
#   - required CLIs (docker, kubectl, minikube)
#   - backend/.env and frontend/.env.local
#   - minikube running
#   - monitoring/workloads namespaces (creates if missing)
#   - Prometheus port-forward on :9090
#
# Cloud one-click deploy (GitHub)
#   - Workflow: .github/workflows/deploy.yml
#   - Trigger: Actions → "One-Click Deploy" → Run workflow
#   - Inputs:
#       environment: staging | production
#       require_smoke: true | false
#
# Required GitHub secrets
#   - AZURE_CREDENTIALS           (service principal JSON)
#   - AZURE_RG                    (resource group for Container Apps)
#   - STAGING_BACKEND_HEALTH_URL  (post-deploy health URL)
#   - PROD_BACKEND_HEALTH_URL     (post-deploy health URL)
#   - SUPABASE_URL                (optional but recommended for smoke gate)
#   - SUPABASE_SERVICE_ROLE_KEY   (optional but recommended for smoke gate)
#
# Promotion gates
#   - Implemented in: backend/promotion/gates.py
#   - Current checks:
#       health_check      (required)
#       smoke_check       (optional via --require-smoke)
#       policy_compliance (placeholder, pass-by-default unless required)
#       budget_check      (optional via BUDGET_LIMIT_USD / CURRENT_MONTHLY_SPEND_USD)
#
# Notes
#   - Keep backend/.env and frontend/.env.local out of git.
#   - Use backend/.env.example and frontend/.env.local.example as templates.
<!-- #{
  "memory_gb": 0.25,
  "energy_preference": "any",
  "gpu_units": null,
  "budget_usd": 2,
  "risk_tolerance": "medium",
  "priority": 3,
  "name": "smoke-e2e-live",
  "latency_sla_ms": 800,
  "cpu_cores": 0.25,
  "container_image": "nginx:stable",
  "failure_prob_sla": 0.2
} -->
