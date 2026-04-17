"""Pareto frontier utilities for scenario filtering."""

from __future__ import annotations

from backend.models import DeploymentScenario


def _dominates(a: DeploymentScenario, b: DeploymentScenario) -> bool:
    """Return True if scenario `a` dominates scenario `b` across all objectives.

    Objectives are minimized:
    - estimated_cost_usd
    - predicted_latency_ms
    - predicted_failure_prob
    - estimated_energy_kwh
    """
    a_vals = (
        a.estimated_cost_usd,
        a.predicted_latency_ms,
        a.predicted_failure_prob,
        a.estimated_energy_kwh,
    )
    b_vals = (
        b.estimated_cost_usd,
        b.predicted_latency_ms,
        b.predicted_failure_prob,
        b.estimated_energy_kwh,
    )
    return all(x <= y for x, y in zip(a_vals, b_vals)) and any(x < y for x, y in zip(a_vals, b_vals))


def filter_dominated_scenarios(scenarios: list[DeploymentScenario]) -> list[DeploymentScenario]:
    if len(scenarios) <= 1:
        return list(scenarios)

    non_dominated: list[DeploymentScenario] = []
    for candidate in scenarios:
        dominated = False
        for other in scenarios:
            if other.scenario_id == candidate.scenario_id:
                continue
            if _dominates(other, candidate):
                dominated = True
                break
        if not dominated:
            non_dominated.append(candidate)
    return non_dominated


def compute_pareto_front(scenarios: list[DeploymentScenario]) -> list[DeploymentScenario]:
    """Alias for filter_dominated_scenarios for clearer intent in call sites."""
    return filter_dominated_scenarios(scenarios)
