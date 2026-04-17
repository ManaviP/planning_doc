"""Multi-agent negotiation engine for scenario selection."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.agents.cost_agent import CostAgent
from backend.agents.energy_agent import EnergyAgent
from backend.agents.latency_agent import LatencyAgent
from backend.agents.risk_agent import RiskAgent
from backend.db import insert_agent_scores, insert_decision
from backend.explainability.reasoning import generate_decision_explanation
from backend.models import (
    AgentScore,
    DecisionResult,
    DeploymentScenario,
    EnergyPreference,
    RiskTolerance,
    WorkloadRequest,
)
from backend.optimization.pareto import compute_pareto_front


class NegotiationEngine:
    DEFAULT_WEIGHTS = {
        "CostAgent": 0.30,
        "RiskAgent": 0.35,
        "LatencyAgent": 0.25,
        "EnergyAgent": 0.10,
    }

    @staticmethod
    def _adapt_weights(workload: WorkloadRequest, base: dict[str, float]) -> dict[str, float]:
        """Return a copy of *base* adjusted for this workload's profile.

        Rules (all additive deltas; result is re-normalised to sum to 1.0):
        - Low risk tolerance   → more weight on RiskAgent
        - High risk tolerance  → more weight on CostAgent (operator is cost-driven)
        - Energy-efficient     → more weight on EnergyAgent
        - Budget constrained   → more weight on CostAgent
        - High priority (≥ 4) → more weight on LatencyAgent (SLA adherence critical)
        """
        w = dict(base)

        # Risk-tolerance adaptation
        risk = workload.risk_tolerance.value if hasattr(workload.risk_tolerance, "value") else str(workload.risk_tolerance)
        if risk == RiskTolerance.LOW.value:
            w["RiskAgent"] = w.get("RiskAgent", 0) + 0.12
            w["CostAgent"] = w.get("CostAgent", 0) - 0.06
            w["EnergyAgent"] = w.get("EnergyAgent", 0) - 0.06
        elif risk == RiskTolerance.HIGH.value:
            w["RiskAgent"] = w.get("RiskAgent", 0) - 0.10
            w["CostAgent"] = w.get("CostAgent", 0) + 0.07
            w["EnergyAgent"] = w.get("EnergyAgent", 0) + 0.03

        # Energy-preference adaptation
        energy = workload.energy_preference.value if hasattr(workload.energy_preference, "value") else str(workload.energy_preference)
        if energy == EnergyPreference.EFFICIENT.value:
            w["EnergyAgent"] = w.get("EnergyAgent", 0) + 0.10
            w["CostAgent"] = w.get("CostAgent", 0) - 0.05
            w["LatencyAgent"] = w.get("LatencyAgent", 0) - 0.05

        # Budget sensitivity
        if workload.budget_usd is not None and workload.budget_usd > 0:
            w["CostAgent"] = w.get("CostAgent", 0) + 0.08
            w["LatencyAgent"] = w.get("LatencyAgent", 0) - 0.04
            w["EnergyAgent"] = w.get("EnergyAgent", 0) - 0.04

        # High-priority latency focus
        if workload.priority >= 4:
            w["LatencyAgent"] = w.get("LatencyAgent", 0) + 0.08
            w["EnergyAgent"] = w.get("EnergyAgent", 0) - 0.04
            w["CostAgent"] = w.get("CostAgent", 0) - 0.04

        # Clamp negatives and normalise
        w = {k: max(v, 0.01) for k, v in w.items()}
        total = sum(w.values())
        return {k: round(v / total, 6) for k, v in w.items()}

    def evaluate(
        self,
        scenarios: list[DeploymentScenario],
        workload: WorkloadRequest,
        weight_overrides: dict | None = None,
    ) -> DecisionResult:
        if not scenarios:
            raise ValueError("At least one scenario is required for negotiation.")

        weights = dict(self.DEFAULT_WEIGHTS)
        if weight_overrides:
            weights.update(weight_overrides)

        # Adapt weights to this workload's profile unless caller supplied overrides
        if not weight_overrides:
            weights = self._adapt_weights(workload, weights)

        agents = [
            CostAgent(scenarios),
            RiskAgent(scenarios),
            LatencyAgent(scenarios),
            EnergyAgent(scenarios),
        ]

        all_scores: list[AgentScore] = []
        final_scores: dict[str, float] = {}

        for scenario in scenarios:
            scenario_scores = [agent.score(scenario, workload) for agent in agents]
            all_scores.extend(scenario_scores)
            final_scores[scenario.scenario_id] = round(
                sum(score.raw_score * weights.get(score.agent_name.value, 0.0) for score in scenario_scores),
                6,
            )

        pareto_candidates = compute_pareto_front(scenarios)
        selection_pool = pareto_candidates or scenarios
        selected_scenario = max(selection_pool, key=lambda scenario: final_scores.get(scenario.scenario_id, float("-inf")))
        weight_summary = ", ".join(f"{k}={v:.2f}" for k, v in weights.items())
        explainability_text = generate_decision_explanation(
            selected=selected_scenario,
            candidates=selection_pool,
            workload=workload,
            final_score=final_scores[selected_scenario.scenario_id],
        )
        decision_reasoning = (
            f"Selected {selected_scenario.scenario_id} on node {selected_scenario.target_node} "
            f"with weighted score {final_scores[selected_scenario.scenario_id]:.4f}. "
            f"Pareto candidates: {len(selection_pool)}/{len(scenarios)}. "
            f"Adapted weights: [{weight_summary}]. "
            f"Workload profile: risk={workload.risk_tolerance}, energy={workload.energy_preference}, "
            f"priority={workload.priority}, budget={'$' + str(workload.budget_usd) if workload.budget_usd else 'unconstrained'}.\n"
            f"{explainability_text}"
        )
        result = DecisionResult(
            workload_id=workload.workload_id,
            selected_scenario_id=selected_scenario.scenario_id,
            all_scenarios=scenarios,
            agent_scores=all_scores,
            final_scores=final_scores,
            decision_reasoning=decision_reasoning,
            decided_at=datetime.now(timezone.utc).isoformat(),
        )

        insert_agent_scores(all_scores)
        insert_decision(result)
        return result
