# AI-Orchestrated Compute Allocation (Simulation-First)

This project is a simulation-driven orchestration platform for AI/ML workloads.

Instead of deploying immediately (reactive orchestration), it first simulates multiple placement strategies, predicts likely outcomes (latency, failure, cost, energy), negotiates trade-offs across multiple objective agents, and only then deploys the chosen strategy to Kubernetes.

It runs with local/free tooling: Docker, Minikube, Prometheus, FastAPI, Supabase, React.

---

## 1) What problem it solves

Traditional autoscaling and scheduling usually reacts after a problem occurs.

This system performs **pre-deployment reasoning**:
- predicts likely workload behavior
- compares candidate nodes and strategies
- chooses best option for workload goals
- preserves decision transparency in dashboard + audit trail

---

## 2) Core design: simulation-first orchestration

For every workload request, the system does:

1. **Collect cluster state** (Prometheus / fallback metrics)
2. **Generate candidate scenarios** (node A/B/C etc.)
3. **Predict outcomes** per scenario
4. **Score via multiple agents** (cost/risk/latency/energy)
5. **Negotiate weighted decision**
6. **Deploy selected scenario** to Kubernetes
7. **Stream logs/events** to frontend + persist in Supabase
8. **Store tamper-evident audit events** (hash chain)

---

## 3) Feature coverage checklist against your target idea

### Already implemented
- ✅ Simulation-first scheduling
- ✅ Multi-agent negotiation (`CostAgent`, `RiskAgent`, `LatencyAgent`, `EnergyAgent`)
- ✅ Predicted latency / failure / cost / energy per scenario
- ✅ Node health metrics collection (CPU, memory, pod count, availability)
- ✅ SLA-aware scoring and decision explainability
- ✅ Kubernetes deployment on selected node
- ✅ React dashboard with cluster, topology, decision, Pareto, logs
- ✅ Local-first stack (Minikube + Docker + Prometheus)
- ✅ Competition mode (two workloads)

### Added/merged now (without removing existing behavior)
- ✅ **YAML workload submission API** (in addition to JSON)
- ✅ **YAML competition submission API**
- ✅ **Tamper-evident audit chain** per workload (`audit_events`)
- ✅ **Audit read + verify endpoints**
- ✅ **Differentiated prediction formulas** to avoid identical scenario outcomes
- ✅ **Adaptive negotiation weights** based on workload profile
- ✅ **Deep learning prediction module** (`backend/prediction/dl_model.py`, PyTorch LSTM)
- ✅ **Automatic prediction fallback** (DL when checkpoint is available, formulas otherwise)
- ✅ **Pareto frontier optimization** before final scenario selection
- ✅ **Explainable decision generator** with structured reasoning text
- ✅ **Periodic learning retrainer** from historical metrics (`backend/learning/trainer.py`)
- ✅ **Interactive What-if Scenario Explorer** in dashboard UI

### Optional future extensions
- 🔶 Temporal Transformer model variant for richer long-range forecasting
- 🔶 Monte Carlo uncertainty simulation per scenario
- 🔶 Reinforcement-learning based scheduling policies

---

## 4) Architecture

### Backend (FastAPI)
- `backend/api/workload.py`: intake + orchestration pipeline
- `backend/scenarios/generator.py`: scenario generation
- `backend/prediction/engine.py`: predictive formulas / ML model hooks
- `backend/prediction/dl_model.py`: deep-learning LSTM train/infer pipeline + checkpoints
- `backend/agents/*.py`: objective-specific scoring
- `backend/optimization/pareto.py`: non-dominated scenario filtering
- `backend/negotiation/engine.py`: multi-agent weighted decision
- `backend/explainability/reasoning.py`: structured decision explanation generation
- `backend/learning/trainer.py`: scheduled model retraining service
- `backend/deployment/manager.py`: Kubernetes deployment and pod tracking
- `backend/websocket/broadcaster.py`: realtime event streaming
- `backend/db.py`: Supabase persistence + audit chain

### Frontend (React + Vite)
- workload submission
- cluster overview and topology
- AI decision panel (reasoning + scenario scores)
- What-if scenario explorer (interactive local recomputation)
- Pareto view for trade-offs
- deployment logs and realtime status

### Data plane
- Prometheus metrics
- Supabase tables for workloads/scenarios/scores/results/logs/metrics/audit

---

## 5) Scoring and prediction formulas

### 5.1 Prediction formulas

Implemented in `backend/prediction/engine.py`.

- Cost estimate combines resource cost + congestion + node-tier multiplier.
- Energy estimate combines workload watts + pressure inefficiency + node efficiency class.
- Failure probability combines pressure, contention, risk profile, priority, node reliability.
- Latency estimate combines queueing delay, memory pressure, contention noise, workload size, node hardware factor.

These are deterministic and node-sensitive, so scenarios diverge meaningfully.

When a trained DL checkpoint is available, `backend/prediction/dl_model.py` provides
LSTM-based predictions (latency/failure/resource demand/congestion), and the engine
automatically prefers DL inference with formula fallback for full backward compatibility.

### 5.2 Agent score formulas (0..100)

- Cost Agent:
	- `score = 100 - (scenario_cost / max_cost_in_batch * 100)`
- Risk Agent:
	- `score = 100 - (predicted_failure_prob * 100)`
- Latency Agent:
	- `score = 100 - min(predicted_latency / latency_sla, 1.0) * 100`
- Energy Agent:
	- `score = 100 - (scenario_energy / max_energy_in_batch * 100)`

### 5.3 Negotiation formula

For each scenario:

`final_score = Σ(agent_score × agent_weight)`

Weights are now adapted dynamically from workload profile (risk tolerance, energy preference, budget, priority), then normalized.

### 5.4 Pareto frontier step

Before choosing the winner, the system filters dominated scenarios using:

- objectives minimized: `cost`, `latency`, `failure_probability`, `energy`
- only non-dominated (Pareto-optimal) scenarios are eligible for final selection

This avoids selecting clearly inferior options even if weighted scores are close.

---

## 6) API reference

### Workload submission
- `POST /workloads` (JSON)
- `POST /workloads/yaml` (YAML string payload)
- `GET /workloads/{workload_id}`
- `GET /workloads`

### Competition mode
- `POST /simulate/competition` (JSON)
- `POST /simulate/competition/yaml` (YAML string payload)

### Results and logs
- `GET /results/{workload_id}`
- `GET /results/{workload_id}/logs`
- `GET /results/{workload_id}/simulation?iterations=300`
- `GET /results/{workload_id}/evaluation`

### Audit trail
- `GET /results/{workload_id}/audit`
- `GET /results/{workload_id}/audit/verify`

### Metrics and health
- `GET /metrics/nodes`
- `GET /health`

### Realtime stream
- `WS /ws/{workload_id}`

---

## 7) YAML payload examples

### 7.1 Single workload via YAML API

Request:

`POST /workloads/yaml`

```json
{
	"yaml_spec": "name: image-inference\ncontainer_image: nginx:stable\ncpu_cores: 0.5\ngpu_units: 0\nmemory_gb: 0.5\nlatency_sla_ms: 700\nfailure_prob_sla: 0.15\nrisk_tolerance: medium\nbudget_usd: 0.5\nenergy_preference: any\npriority: 3"
}
```

### 7.2 Competition via YAML API

Request:

`POST /simulate/competition/yaml`

```json
{
	"yaml_spec": "workload_a:\n  name: critical-inference\n  container_image: nginx:stable\n  cpu_cores: 1\n  gpu_units: 0\n  memory_gb: 1\n  latency_sla_ms: 450\n  failure_prob_sla: 0.08\n  risk_tolerance: low\n  budget_usd: 1.2\n  energy_preference: balanced\n  priority: 5\nworkload_b:\n  name: batch-embedding\n  container_image: nginx:stable\n  cpu_cores: 0.7\n  gpu_units: 0\n  memory_gb: 0.8\n  latency_sla_ms: 1200\n  failure_prob_sla: 0.2\n  risk_tolerance: high\n  budget_usd: 0.4\n  energy_preference: efficient\n  priority: 2"
}
```

---

## 8) Auditability and tamper evidence

Each major workload lifecycle event writes an `audit_events` record containing:
- `previous_hash`
- `event_hash` (SHA-256 over canonical event payload + previous hash)

This gives a **tamper-evident chain** per workload.

Use:
- `GET /results/{workload_id}/audit` for raw events
- `GET /results/{workload_id}/audit/verify` to validate chain continuity

---

## 9) Run

Use [RUNBOOK.md](RUNBOOK.md) for setup and start steps.

Quick check:
- Backend: `http://localhost:8000/health`
- Frontend: `http://localhost:3000`
- Model evaluation page (example): `http://localhost:3000/evaluation/<workload_id>`

