from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.api.workload as workload_api
from backend.models import DeploymentScenario, NodeMetrics


def _workload_record(workload_id: str = "w1") -> dict:
    return {
        "workload_id": workload_id,
        "name": "test-workload",
        "container_image": "nginx:stable",
        "cpu_cores": 0.25,
        "gpu_units": None,
        "memory_gb": 0.25,
        "latency_sla_ms": 800,
        "failure_prob_sla": 0.2,
        "risk_tolerance": "medium",
        "budget_usd": 2,
        "energy_preference": "any",
        "priority": 3,
        "submitted_at": "2026-04-15T00:00:00Z",
        "status": "pending",
    }


def _decision_payload(workload_id: str = "w1") -> dict:
    return {
        "workload_id": workload_id,
        "selected_scenario_id": "s1",
        "all_scenarios": [
            {
                "scenario_id": "s1",
                "workload_id": workload_id,
                "target_node": "minikube-m01",
                "predicted_latency_ms": 120.0,
                "predicted_failure_prob": 0.08,
                "estimated_cost_usd": 1.2,
                "estimated_energy_kwh": 0.3,
            }
        ],
    }


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(workload_api.router)
    return TestClient(app)


def test_deploy_endpoint_valid_cloud_returns_workflow_url(monkeypatch):
    monkeypatch.setattr(workload_api, "get_workload", lambda workload_id: _workload_record(workload_id))
    monkeypatch.setattr(workload_api, "get_decision", lambda workload_id: _decision_payload(workload_id))
    monkeypatch.setattr(workload_api, "update_workload_status", lambda workload_id, status: None)
    monkeypatch.setattr(workload_api, "insert_log", lambda workload_id, message, level: None)

    states: list[dict] = []

    def fake_set_state(workload_id: str, **kwargs):
        snapshot = {"workload_id": workload_id, **kwargs}
        states.append(snapshot)
        return snapshot

    monkeypatch.setattr(workload_api, "_set_deployment_state", fake_set_state)
    monkeypatch.setattr(
        workload_api,
        "_trigger_github_actions_dispatch",
        lambda workload_id, target: {
            "environment": target,
            "workflow_url": "https://github.com/acme/allocator/actions/workflows/deploy.yml",
            "run_url": "https://github.com/acme/allocator/actions/runs/123",
        },
    )

    client = _client()
    response = client.post("/workloads/w1/deploy", json={"target": "staging"})

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "deploying"
    assert payload["target"] == "staging"
    assert payload["run_url"].endswith("/123")
    assert any(s.get("state") == "queued" for s in states)
    assert any(s.get("state") == "triggered" for s in states)


def test_deploy_endpoint_invalid_missing_workload_returns_404(monkeypatch):
    monkeypatch.setattr(workload_api, "get_workload", lambda workload_id: None)

    client = _client()
    response = client.post("/workloads/missing/deploy", json={"target": "staging"})

    assert response.status_code == 404


def test_retry_endpoint_failed_to_deploying(monkeypatch):
    monkeypatch.setattr(workload_api, "get_workload", lambda workload_id: _workload_record(workload_id))
    monkeypatch.setattr(
        workload_api,
        "get_latest_deployment_state",
        lambda workload_id: {"state": "failed", "target": "local", "mode": "local"},
    )
    monkeypatch.setattr(workload_api, "insert_log", lambda workload_id, message, level: None)

    def fake_deploy(workload_id, payload, background_tasks):
        return {
            "status": "deploying",
            "workload_id": workload_id,
            "target": payload.target,
            "message": "Deployment triggered.",
        }

    monkeypatch.setattr(workload_api, "deploy_workload", fake_deploy)

    client = _client()
    response = client.post("/workloads/w1/deploy/retry", json={})

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "deploying"
    assert body["target"] == "local"


def test_cancel_endpoint_sets_cancelled(monkeypatch):
    monkeypatch.setattr(workload_api, "get_workload", lambda workload_id: _workload_record(workload_id))
    monkeypatch.setattr(
        workload_api,
        "get_latest_deployment_state",
        lambda workload_id: {"state": "deploying", "target": "local", "mode": "local"},
    )

    statuses: list[str] = []

    monkeypatch.setattr(workload_api, "update_workload_status", lambda workload_id, status: statuses.append(status))
    monkeypatch.setattr(workload_api, "insert_log", lambda workload_id, message, level: None)

    captured: dict = {}

    def fake_set_state(workload_id: str, **kwargs):
        captured.update(kwargs)
        return {"workload_id": workload_id, **kwargs}

    monkeypatch.setattr(workload_api, "_set_deployment_state", fake_set_state)

    client = _client()
    response = client.post("/workloads/w1/deploy/cancel", json={"reason": "Cancel from test"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["deploy_state"] == "cancelled"
    assert statuses[-1] == "ready_for_deployment"
    assert captured["state"] == "cancelled"


def test_github_dispatch_failure_returns_503(monkeypatch):
    monkeypatch.setattr(workload_api, "get_workload", lambda workload_id: _workload_record(workload_id))
    monkeypatch.setattr(workload_api, "get_decision", lambda workload_id: _decision_payload(workload_id))
    monkeypatch.setattr(workload_api, "update_workload_status", lambda workload_id, status: None)
    monkeypatch.setattr(workload_api, "insert_log", lambda workload_id, message, level: None)
    monkeypatch.setattr(workload_api, "_set_deployment_state", lambda workload_id, **kwargs: None)

    def fail_dispatch(workload_id: str, target: str):
        raise RuntimeError("Missing GITHUB_REPOSITORY or GITHUB_TOKEN")

    monkeypatch.setattr(workload_api, "_trigger_github_actions_dispatch", fail_dispatch)

    client = _client()
    response = client.post("/workloads/w1/deploy", json={"target": "staging"})

    assert response.status_code == 503
    assert "Cloud deployment trigger failed" in response.json()["detail"]


def test_k8s_unavailable_returns_ready_for_deployment(monkeypatch):
    statuses: list[str] = []

    monkeypatch.setattr(workload_api, "get_workload", lambda workload_id: _workload_record(workload_id))
    monkeypatch.setattr(workload_api, "update_workload_status", lambda workload_id, status: statuses.append(status))
    monkeypatch.setattr(workload_api, "insert_log", lambda workload_id, message, level: None)
    monkeypatch.setattr(workload_api, "_emit", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        workload_api,
        "collect_node_metrics",
        lambda: [
            NodeMetrics(
                node_name="minikube-m01",
                cpu_usage_pct=50.0,
                memory_usage_pct=50.0,
                pod_count=1,
                available=True,
                collected_at="2026-04-15T00:00:00Z",
                gpu_usage_pct=None,
            )
        ],
    )

    scenarios = [
        DeploymentScenario(
            scenario_id="s1",
            workload_id="w1",
            target_node="minikube-m01",
            predicted_latency_ms=120.0,
            predicted_failure_prob=0.08,
            estimated_cost_usd=1.2,
            estimated_energy_kwh=0.3,
        )
    ]
    monkeypatch.setattr(workload_api, "generate_scenarios", lambda workload, nodes: scenarios)

    @dataclass
    class _Decision:
        selected_scenario_id: str = "s1"
        final_scores: dict = None
        agent_scores: list = None

        def __post_init__(self):
            if self.final_scores is None:
                self.final_scores = {"s1": 0.95}
            if self.agent_scores is None:
                self.agent_scores = []

    class _Negotiator:
        def evaluate(self, scs, wl):
            return _Decision()

    monkeypatch.setattr(workload_api, "NegotiationEngine", lambda: _Negotiator())

    class _FailingManager:
        def __init__(self):
            raise workload_api.DeploymentError("Unable to initialize Kubernetes client: boom")

    monkeypatch.setattr(workload_api, "DeploymentManager", _FailingManager)

    result = workload_api.run_allocation_pipeline("w1")

    assert result["status"] == "ready_for_deployment"
    assert "evaluating" in statuses
    assert "ready_for_deployment" in statuses


def test_deploy_status_endpoint_returns_persisted_state(monkeypatch):
    monkeypatch.setattr(workload_api, "get_workload", lambda workload_id: _workload_record(workload_id))
    monkeypatch.setattr(
        workload_api,
        "get_latest_deployment_state",
        lambda workload_id: {
            "run_id": "run-1",
            "state": "triggered",
            "target": "staging",
            "mode": "cloud",
            "message": "Workflow dispatched",
            "workflow_url": "https://github.com/acme/allocator/actions/workflows/deploy.yml",
            "run_url": "https://github.com/acme/allocator/actions/runs/123",
            "updated_at": "2026-04-15T00:00:00Z",
        },
    )

    client = _client()
    response = client.get("/workloads/w1/deploy/status")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "triggered"
    assert body["mode"] == "cloud"
    assert body["run_id"] == "run-1"
