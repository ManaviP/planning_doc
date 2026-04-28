"""Monte Carlo scenario simulation for what-if confidence analysis."""

from __future__ import annotations

import random
from dataclasses import dataclass

from backend.models import NodeMetrics, WorkloadRequest
from backend.prediction.engine import predict_failure_prob, predict_latency, predict_resource_demand


@dataclass
class MonteCarloResult:
    iterations: int
    latency_ms_mean: float
    latency_ms_p95: float
    failure_prob_mean: float
    failure_prob_p95: float
    demand_mean: float
    sla_breach_rate: float


_DEF_CPU_SIGMA = 6.0
_DEF_MEM_SIGMA = 6.0
_DEF_POD_SIGMA = 2.0


def _clamp(value: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(value, max_v))


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * q))
    idx = max(0, min(idx, len(ordered) - 1))
    return float(ordered[idx])


def _perturbed(node: NodeMetrics) -> NodeMetrics:
    return NodeMetrics(
        node_name=node.node_name,
        cpu_usage_pct=_clamp(random.gauss(node.cpu_usage_pct, _DEF_CPU_SIGMA), 0.0, 100.0),
        memory_usage_pct=_clamp(random.gauss(node.memory_usage_pct, _DEF_MEM_SIGMA), 0.0, 100.0),
        gpu_usage_pct=node.gpu_usage_pct,
        pod_count=int(_clamp(random.gauss(node.pod_count, _DEF_POD_SIGMA), 0.0, 300.0)),
        available=node.available,
        collected_at=node.collected_at,
    )


def run_monte_carlo(workload: WorkloadRequest, node: NodeMetrics, iterations: int = 200) -> MonteCarloResult:
    n = int(_clamp(iterations, 20, 5000))

    latencies: list[float] = []
    failures: list[float] = []
    demands: list[float] = []

    for _ in range(n):
        sample = _perturbed(node)
        latencies.append(float(predict_latency(workload, sample, use_dl=False)))
        failures.append(float(predict_failure_prob(workload, sample, use_dl=False)))
        demands.append(float(predict_resource_demand(workload, sample, use_dl=False)))

    sla_breach = sum(1 for x in latencies if x > workload.latency_sla_ms)

    return MonteCarloResult(
        iterations=n,
        latency_ms_mean=round(sum(latencies) / n, 4),
        latency_ms_p95=round(_percentile(latencies, 0.95), 4),
        failure_prob_mean=round(sum(failures) / n, 6),
        failure_prob_p95=round(_percentile(failures, 0.95), 6),
        demand_mean=round(sum(demands) / n, 6),
        sla_breach_rate=round(sla_breach / n, 6),
    )
