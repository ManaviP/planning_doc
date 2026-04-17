"""Energy-efficiency-oriented scenario scorer."""

from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.models import AgentName, AgentScore, DeploymentScenario, WorkloadRequest


class EnergyAgent(BaseAgent):
    def __init__(self, scenarios: list[DeploymentScenario]) -> None:
        super().__init__(scenarios)
        self.max_energy = max((scenario.estimated_energy_kwh for scenario in scenarios), default=1.0) or 1.0
        self.min_energy = min((scenario.estimated_energy_kwh for scenario in scenarios), default=0.0)

    def score(self, scenario: DeploymentScenario, workload: WorkloadRequest) -> AgentScore:
        raw_score = 100 - (scenario.estimated_energy_kwh / self.max_energy * 100)
        normalized = max(0.0, min(100.0, raw_score))
        energy_range = self.max_energy - self.min_energy
        relative_pct = (scenario.estimated_energy_kwh - self.min_energy) / energy_range * 100 if energy_range > 1e-9 else 50.0
        pref = workload.energy_preference.value if hasattr(workload.energy_preference, "value") else str(workload.energy_preference)
        pref_note = f" (energy-efficient placement prioritised)" if pref == "efficient" else ""
        if normalized >= 70:
            tier = "green placement"
        elif normalized >= 40:
            tier = "average energy draw"
        else:
            tier = "energy-intensive"
        reasoning = (
            f"Node {scenario.target_node}: {scenario.estimated_energy_kwh:.4f}kWh "
            f"(batch range {self.min_energy:.4f}–{self.max_energy:.4f}kWh, "
            f"{relative_pct:.0f}th percentile){pref_note}. "
            f"Score {normalized:.2f}/100 — {tier}."
        )
        return AgentScore(
            scenario_id=scenario.scenario_id,
            workload_id=workload.workload_id,
            agent_name=AgentName.ENERGY_AGENT,
            raw_score=round(normalized, 4),
            reasoning=reasoning,
        )
