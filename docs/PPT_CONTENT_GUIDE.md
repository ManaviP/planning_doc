# Optimizing Compute Orchestrator - PPT Content Guide

Use this file to copy content directly into your slides.
Language is kept simple and easy to speak.

## 0) First Pitch (Opening 30-40 seconds)
Our project solves one common cloud problem: wrong workload placement.
Today, many systems place apps first and fix issues later.
That causes delay, failure risk, and extra cloud cost.
We built an AI-Orchestrated Compute Allocator that predicts what may happen before deployment.
It simulates multiple node options, scores them for cost, risk, latency, and energy, then picks the best one.
It also gives clear reasoning and keeps audit logs.
So this is not just monitoring, it is proactive decision support for cloud allocation.

## 1) Abstract (One Paragraph ~100 words)
Cloud systems often place workloads first and react only after slowdowns or failures. This leads to higher cost, unstable performance, and difficult operations. Our project, AI-Orchestrated Compute Allocation, solves this with a simulation-first approach. Before deployment, it collects node metrics, creates possible placement scenarios, predicts latency, failure risk, cost, and energy, and ranks options using multi-agent negotiation. It then selects a Pareto-optimal scenario and provides clear explainable reasoning. The system supports JSON and YAML APIs, dashboard visualization, deployment flow, and audit verification. Expected outcomes are better SLA handling, lower cloud waste, safer deployment decisions, and more transparent infrastructure planning.

## 2) Problem Statement
Problem: Teams deploying workloads on clusters often do not know which node is best, so they face either app failures (under-provisioning) or unnecessary cost (over-provisioning).

Solution: Build a simulation-first allocator using FastAPI + prediction models + multi-agent scoring to choose the best node before deployment.

## 3) Objectives
### Main goals
- Predict workload outcomes before deployment (latency, failure, cost, energy).
- Compare multiple placement scenarios instead of one direct schedule.
- Use multi-agent scoring (Cost, Risk, Latency, Energy) for balanced decisions.
- Apply Pareto filtering so clearly bad scenarios are removed.
- Show explainable reasoning and maintain tamper-evident audit records.

### Expected outcomes
- More stable workload allocation decisions.
- Better SLA compliance.
- Lower resource waste and better cost control.
- Better trust through transparent and auditable decisions.

## 4) Introduction
### Current status
Most schedulers are reactive. They use current cluster state, but do not fully estimate future behavior of each placement option.

### What we plan to do
Add an intelligent decision layer before deployment. This layer simulates options and picks the best one based on workload goals.

### Scope
- Workload intake APIs (JSON and YAML)
- Scenario generation and prediction
- Multi-agent negotiation and Pareto optimization
- Explainability and audit verification
- Dashboard and deployment status flow

### Assumptions
- Metrics are available from Prometheus or synthetic fallback.
- Workload requirements (SLA, budget, priority) are provided.
- Kubernetes target environment is available for deployment actions.

## 5) Literature Survey (State of the Art Work)
Use this as a simple comparison table in PPT.

| Area | Existing Idea | Limitation in Existing Work | How Our Project Uses/Improves It |
|---|---|---|---|
| Container scheduling | Kubernetes scheduler | Mostly immediate placement, less future simulation | Added simulation-first evaluation before final choice |
| Cluster prediction | Time-series models like LSTM | Often prediction-only, not full allocation pipeline | Combined prediction with scenario scoring and selection |
| Fallback modeling | Tree models like Random Forest | Usually separate from orchestration | Kept as optional fallback model path in prediction module |
| Multi-objective optimization | Pareto-based trade-off analysis | Often hard for operators to consume directly | Added Pareto + weighted agent negotiation + explanation |
| Reliable operations | CI/CD health gates | Focuses on deployment, not allocation quality | Added promotion gates and health checks to deployment flow |

## 6) Social / Environmental Impact
This project can reduce cloud waste by avoiding poor placement decisions.
It includes energy-aware scoring, so operators can choose more efficient scenarios and support greener compute usage.

## 7) Proposed Methodology
### Work done and flow
1. Collect node metrics (Prometheus, else synthetic fallback).
2. Generate candidate scenarios for target nodes.
3. Predict outcome metrics for each scenario.
4. Score with Cost, Risk, Latency, and Energy agents.
5. Apply Pareto frontier to remove dominated scenarios.
6. Run weighted negotiation and choose final scenario.
7. Save results, logs, and audit chain.

### Data collection
- Node metrics: CPU, memory, pod count, availability, optional GPU.
- Historical snapshots from database for model training/inference.

### Data preparation
- Build windowed time-series samples for model input.
- Normalize/transform feature values.
- Use fallback formulas when model or history is insufficient.

## 8) Design & Implementation
### System architecture
- Frontend: React + Vite dashboard.
- Backend: FastAPI orchestration APIs.
- Prediction layer: Formula engine + LSTM model + optional RF fallback.
- Optimization layer: Multi-agent scoring + Pareto filtering + negotiation.
- Data layer: Supabase for workloads, results, logs, metrics, and audit events.
- Deployment layer: Kubernetes/Minikube integration.

### Database design (high level)
Main entities include workloads, scenarios, decision_results, log_entries, node_metrics_snapshots, audit_events.

### Module relation (simple)
API -> Scenario Generator -> Prediction -> Agent Scoring -> Pareto -> Negotiation -> Decision + Explanation -> Deployment + Logs.

### Tools and technologies
- Python, FastAPI, PyTorch, scikit-learn
- React, Vite, Recharts
- Docker, Docker Compose, Minikube, Kubernetes
- Supabase, Prometheus

### Modules developed
- workload APIs
- prediction engine (formula + ML)
- negotiation engine
- pareto optimizer
- explainability module
- promotion gates
- deployment manager

### Screenshots to include in PPT
- Workload form
- Cluster overview/topology
- AI decision panel
- Pareto graph
- Deployment logs
- Model evaluation page

## 9) Demo (Very Important)
Use this exact order in presentation:
1. Open dashboard and show cluster status.
2. Submit one workload from Workload Form.
3. Show generated scenarios and predicted values.
4. Show agent scores and final chosen scenario.
5. Show explainability text (why this node was selected).
6. Open Pareto graph and explain trade-offs.
7. Show deployment status/logs page.
8. Show audit verification endpoint output.

### Live commands (optional demo backup)
- docker compose up -d --build
- Open http://localhost:3000
- Health check: http://localhost:8000/health

## 10) Results & Discussion
### Output
- System returns ranked scenarios and a final selected scenario.
- Explanation text is generated for decision transparency.
- Audit chain verification endpoint supports trust checks.

### Performance/validation notes
- Frontend build is successful.
- Deployment-flow tests pass in backend test suite.
- Backend and frontend health endpoints respond correctly in Docker run.

### Comparison with baseline schedulers
- Default schedulers: mostly reactive and single-objective.
- Our system: predictive, multi-objective, explainable, and audit-aware.

## 11) Conclusion
We built a working simulation-first allocation system that improves decision quality before deployment.
It combines prediction, multi-agent negotiation, Pareto optimization, explainability, and deployment safety checks.
This makes cloud allocation more practical, transparent, and aligned to cost/SLA/energy goals.

## 12) Future Scope
- Stronger model monitoring and drift alerts.
- Distributed simulation workers for larger clusters.
- Better real-time cost inputs from cloud billing APIs.
- Multi-cluster and hybrid-cloud scheduling support.
- More real production traces for model training quality.

## 13) References (Simple and Safe)
Use these as base references and format in your college citation style.

1. Kubernetes Documentation - Scheduling, Deployments, and Cluster Concepts.
2. FastAPI Documentation - API design and async backend patterns.
3. PyTorch Documentation - LSTM model development and inference.
4. Scikit-learn Documentation - Random Forest model support.
5. Prometheus Documentation - Metrics collection and query model.
6. Supabase Documentation - Postgres-backed API and storage.
7. Pareto Optimization concepts from standard multi-objective optimization literature.

## 14) Viva Short Answers (Quick Use)
### Why this project is unique?
Because it predicts and compares options before deployment, not after failure.

### Why better than default scheduler?
It supports cost, risk, latency, and energy together, with clear explanation.

### Real value?
Lower risk, better SLA support, and better cloud cost decisions.

### Honest limitation?
Quality depends on metrics quality and historical data coverage.

### One-line closing
From reactive scheduling to proactive, explainable allocation.
