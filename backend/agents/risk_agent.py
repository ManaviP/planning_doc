"""Failure-risk-oriented scenario scorer."""

from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.models import AgentName, AgentScore, DeploymentScenario, WorkloadRequest


class RiskAgent(BaseAgent):
    def score(self, scenario: DeploymentScenario, workload: WorkloadRequest) -> AgentScore:
        raw_score = 100 - (scenario.predicted_failure_prob * 100)
        normalized = max(0.0, min(100.0, raw_score))
        prob_pct = scenario.predicted_failure_prob * 100
        sla_pct = workload.failure_prob_sla * 100
        within_sla = scenario.predicted_failure_prob <= workload.failure_prob_sla
        sla_status = "within SLA" if within_sla else f"exceeds SLA by {prob_pct - sla_pct:.1f} pp"
        if normalized >= 80:
            tier = "low-risk"
        elif normalized >= 60:
            tier = "moderate-risk"
        elif normalized >= 40:
            tier = "elevated-risk"
        else:
            tier = "high-risk"
        reasoning = (
            f"Node {scenario.target_node}: predicted failure probability {prob_pct:.2f}% "
            f"vs workload SLA {sla_pct:.1f}% ({sla_status}). "
            f"Score {normalized:.2f}/100 — {tier} placement."
        )
        return AgentScore(
            scenario_id=scenario.scenario_id,
            workload_id=workload.workload_id,
            agent_name=AgentName.RISK_AGENT,
            raw_score=round(normalized, 4),
            reasoning=reasoning,
        )
