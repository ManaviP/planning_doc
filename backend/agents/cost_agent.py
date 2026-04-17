"""Cost-oriented scenario scorer."""

from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.models import AgentName, AgentScore, DeploymentScenario, WorkloadRequest


class CostAgent(BaseAgent):
    def __init__(self, scenarios: list[DeploymentScenario]) -> None:
        super().__init__(scenarios)
        self.max_cost = max((scenario.estimated_cost_usd for scenario in scenarios), default=1.0) or 1.0
        self.min_cost = min((scenario.estimated_cost_usd for scenario in scenarios), default=0.0)

    def score(self, scenario: DeploymentScenario, workload: WorkloadRequest) -> AgentScore:
        raw_score = 100 - (scenario.estimated_cost_usd / self.max_cost * 100)
        normalized = max(0.0, min(100.0, raw_score))
        cost_range = self.max_cost - self.min_cost
        relative_pct = (scenario.estimated_cost_usd - self.min_cost) / cost_range * 100 if cost_range > 1e-9 else 50.0
        if normalized >= 70:
            verdict = "cost-efficient node"
        elif normalized >= 40:
            verdict = "moderate cost"
        else:
            verdict = "expensive node"
        reasoning = (
            f"Node {scenario.target_node}: ${scenario.estimated_cost_usd:.4f}/hr "
            f"(batch range ${self.min_cost:.4f}–${self.max_cost:.4f}, "
            f"{relative_pct:.0f}th percentile within batch). "
            f"Score {normalized:.2f}/100 — {verdict}."
        )
        return AgentScore(
            scenario_id=scenario.scenario_id,
            workload_id=workload.workload_id,
            agent_name=AgentName.COST_AGENT,
            raw_score=round(normalized, 4),
            reasoning=reasoning,
        )
