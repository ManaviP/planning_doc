"""Deployment scenario generation for candidate compute allocations."""

from __future__ import annotations

from backend.db import insert_scenarios
from backend.models import DeploymentScenario, NodeMetrics, WorkloadRequest
from backend.prediction.engine import (
    build_feature_vector,
    estimate_cost,
    estimate_energy,
    load_latency_model,
    predict_failure_prob,
    predict_latency,
    predict_latency_ml,
)


class NoViableNodeError(RuntimeError):
    """Raised when no node can safely host a workload."""


def _eligible_nodes(nodes: list[NodeMetrics], threshold_pct: float) -> list[NodeMetrics]:
    return [
        node
        for node in nodes
        if node.available and node.cpu_usage_pct <= threshold_pct and node.memory_usage_pct <= threshold_pct
    ]


def _scenario_id(workload_id: str, node_name: str) -> str:
    safe_node_name = node_name.replace(" ", "-")
    return f"scenario_{workload_id}_{safe_node_name}"


def generate_scenarios(workload: WorkloadRequest, nodes: list[NodeMetrics]) -> list[DeploymentScenario]:
    viable_nodes = _eligible_nodes(nodes, threshold_pct=90.0)
    if not viable_nodes:
        viable_nodes = _eligible_nodes(nodes, threshold_pct=95.0)
    if not viable_nodes:
        raise NoViableNodeError(f"No viable nodes available for workload {workload.workload_id}.")

    latency_model = load_latency_model()
    scenarios: list[DeploymentScenario] = []

    for node in viable_nodes:
        features = build_feature_vector(workload, node)
        predicted_latency_ms = (
            predict_latency_ml(features, latency_model)
            if latency_model is not None
            else predict_latency(workload, node)
        )
        scenario = DeploymentScenario(
            scenario_id=_scenario_id(workload.workload_id, node.node_name),
            workload_id=workload.workload_id,
            target_node=node.node_name,
            predicted_latency_ms=predicted_latency_ms,
            predicted_failure_prob=predict_failure_prob(workload, node),
            estimated_cost_usd=estimate_cost(workload, node),
            estimated_energy_kwh=estimate_energy(workload, node),
        )
        scenarios.append(scenario)

    scenarios.sort(key=lambda item: item.estimated_cost_usd)
    insert_scenarios(scenarios)
    return scenarios
