"""Latency-SLA-oriented scenario scorer."""

from __future__ import annotations

from backend.agents.base import BaseAgent
from backend.models import AgentName, AgentScore, DeploymentScenario, WorkloadRequest


class LatencyAgent(BaseAgent):
    def score(self, scenario: DeploymentScenario, workload: WorkloadRequest) -> AgentScore:
        sla_ms = max(float(workload.latency_sla_ms), 1.0)
        raw_score = 100 - min(scenario.predicted_latency_ms / sla_ms, 1.0) * 100
        normalized = max(0.0, min(100.0, raw_score))
        headroom_ms = sla_ms - scenario.predicted_latency_ms
        headroom_pct = headroom_ms / sla_ms * 100
        within_sla = scenario.predicted_latency_ms <= sla_ms
        if normalized >= 80:
            tier = "well within SLA"
        elif normalized >= 50:
            tier = "acceptable latency"
        elif within_sla:
            tier = "tight SLA margin"
        else:
            tier = "SLA breach risk"
        reasoning = (
            f"Node {scenario.target_node}: predicted p95 latency {scenario.predicted_latency_ms:.1f}ms "
            f"vs SLA {sla_ms:.0f}ms "
            f"({'headroom ' + f'{headroom_pct:.1f}%' if within_sla else f'over by {-headroom_ms:.1f}ms'}). "
            f"Score {normalized:.2f}/100 — {tier}."
        )
        return AgentScore(
            scenario_id=scenario.scenario_id,
            workload_id=workload.workload_id,
            agent_name=AgentName.LATENCY_AGENT,
            raw_score=round(normalized, 4),
            reasoning=reasoning,
        )
