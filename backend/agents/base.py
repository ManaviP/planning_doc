"""Base contracts for workload allocation scoring agents."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.models import AgentScore, DeploymentScenario, WorkloadRequest


class BaseAgent(ABC):
    def __init__(self, scenarios: list[DeploymentScenario]) -> None:
        self.scenarios = scenarios

    @abstractmethod
    def score(self, scenario: DeploymentScenario, workload: WorkloadRequest) -> AgentScore:
        """Return a normalized score from 0 to 100 where higher is better."""
