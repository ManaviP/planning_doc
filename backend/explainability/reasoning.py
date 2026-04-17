"""Structured explainability helpers for deployment decisions."""

from __future__ import annotations

from backend.models import DeploymentScenario, WorkloadRequest


def _pct_improvement(reference: float, candidate: float) -> float:
    if reference <= 1e-9:
        return 0.0
    return (reference - candidate) / reference * 100.0


def generate_decision_explanation(
    selected: DeploymentScenario,
    candidates: list[DeploymentScenario],
    workload: WorkloadRequest,
    final_score: float,
) -> str:
    """Generate a compact, structured explanation string for persisted decisions."""
    if not candidates:
        return f"Decision Explanation: {selected.target_node} selected with score {final_score:.2f}."

    avg_latency = sum(c.predicted_latency_ms for c in candidates) / len(candidates)
    avg_failure = sum(c.predicted_failure_prob for c in candidates) / len(candidates)
    avg_cost = sum(c.estimated_cost_usd for c in candidates) / len(candidates)
    avg_energy = sum(c.estimated_energy_kwh for c in candidates) / len(candidates)

    latency_gain = _pct_improvement(avg_latency, selected.predicted_latency_ms)
    failure_gain = _pct_improvement(avg_failure, selected.predicted_failure_prob)
    cost_gain = _pct_improvement(avg_cost, selected.estimated_cost_usd)
    energy_gain = _pct_improvement(avg_energy, selected.estimated_energy_kwh)

    budget_ok = workload.budget_usd is None or selected.estimated_cost_usd <= workload.budget_usd

    lines = [
        "Decision Explanation:",
        f"- Node {selected.target_node} selected with final score {final_score:.2f}.",
        f"- Predicted latency improvement vs scenario average: {latency_gain:.1f}%.",
        f"- Predicted failure reduction vs scenario average: {failure_gain:.1f}%.",
        f"- Cost improvement vs scenario average: {cost_gain:.1f}%.",
        f"- Energy improvement vs scenario average: {energy_gain:.1f}%.",
        f"- Budget constraint: {'within budget' if budget_ok else 'above budget'}.",
        f"- Risk tolerance: {workload.risk_tolerance.value}. Energy preference: {workload.energy_preference.value}.",
    ]
    return "\n".join(lines)
