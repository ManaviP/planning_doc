"""Domain models for the compute allocator backend."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class WorkloadStatus(str, enum.Enum):
	PENDING = "pending"
	EVALUATING = "evaluating"
	READY_FOR_DEPLOYMENT = "ready_for_deployment"
	DEPLOYING = "deploying"
	DEPLOYED = "deployed"
	FAILED = "failed"
	DELAYED = "delayed"


class RiskTolerance(str, enum.Enum):
	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"


class EnergyPreference(str, enum.Enum):
	EFFICIENT = "efficient"
	BALANCED = "balanced"
	ANY = "any"


class AgentName(str, enum.Enum):
	COST_AGENT = "CostAgent"
	RISK_AGENT = "RiskAgent"
	LATENCY_AGENT = "LatencyAgent"
	ENERGY_AGENT = "EnergyAgent"


class WebSocketEventType(str, enum.Enum):
	SCENARIO_GENERATED = "scenario_generated"
	AGENT_SCORED = "agent_scored"
	DECISION_MADE = "decision_made"
	DEPLOYMENT_STARTED = "deployment_started"
	POD_STATUS_UPDATE = "pod_status_update"
	DEPLOYMENT_SUCCESS = "deployment_success"
	DEPLOYMENT_FAILED = "deployment_failed"
	LOG_LINE = "log_line"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class WorkloadRequest:
	"""A workload submission with resource requirements and SLA constraints."""

	workload_id: str
	name: str
	container_image: str
	cpu_cores: float
	memory_gb: float
	latency_sla_ms: int
	failure_prob_sla: float
	risk_tolerance: RiskTolerance
	energy_preference: EnergyPreference
	priority: int
	submitted_at: str
	status: WorkloadStatus
	gpu_units: float | None = None
	budget_usd: float | None = None


@dataclass
class NodeMetrics:
	"""Snapshot of a Kubernetes node's resource utilisation."""

	node_name: str
	cpu_usage_pct: float
	memory_usage_pct: float
	pod_count: int
	available: bool
	collected_at: str
	gpu_usage_pct: float | None = None


@dataclass
class DeploymentScenario:
	"""A candidate placement of a workload onto a specific node."""

	scenario_id: str
	workload_id: str
	target_node: str
	predicted_latency_ms: float
	predicted_failure_prob: float
	estimated_cost_usd: float
	estimated_energy_kwh: float


@dataclass
class AgentScore:
	"""A single agent's score for one scenario."""

	scenario_id: str
	workload_id: str
	agent_name: AgentName
	raw_score: float
	reasoning: str


@dataclass
class DecisionResult:
	"""The final negotiated decision after all agents have scored all scenarios."""

	workload_id: str
	selected_scenario_id: str
	all_scenarios: list[DeploymentScenario]
	agent_scores: list[AgentScore]
	final_scores: dict[str, float]
	decision_reasoning: str
	decided_at: str | None = None


@dataclass
class WebSocketEvent:
	"""A real-time event pushed to subscribed WebSocket clients."""

	event_type: WebSocketEventType
	workload_id: str
	payload: dict[str, Any]
	timestamp: str | None = None
