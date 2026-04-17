"""Feature engineering and prediction functions for workload scenario scoring.

Each function is designed to produce *differentiated* values across nodes so
that the downstream scoring agents can surface meaningful trade-offs.  Node
variation is achieved through three complementary mechanisms:

1. **Pressure factor** – CPU + memory utilisation naturally varies between
   nodes and creates the dominant signal.
2. **Contention factor** – pod count adds an independent scheduling-noise
   dimension.
3. **Deterministic node jitter** – a stable hash of the node name yields a
   consistent hardware-tier offset (e.g. network proximity, disk speed, power
   efficiency class) without any randomness across runs.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from backend.db import get_metrics_history
from backend.models import NodeMetrics, WorkloadRequest
from backend.prediction.dl_model import WINDOW as DL_WINDOW
from backend.prediction.dl_model import infer as dl_infer
from backend.prediction.dl_model import load_trained_model

# ---------------------------------------------------------------------------
# Cloud-pricing reference rates
# ---------------------------------------------------------------------------
_CPU_COST_USD_PER_CORE_HOUR: float = 0.048
_MEM_COST_USD_PER_GB_HOUR: float = 0.006
_GPU_COST_USD_PER_UNIT_HOUR: float = 0.90

# ---------------------------------------------------------------------------
# Energy constants  (simplified PUE = 1.2 data-centre model)
# ---------------------------------------------------------------------------
_CPU_WATTS_PER_CORE: float = 15.0
_MEM_WATTS_PER_GB: float = 0.375
_GPU_WATTS_PER_UNIT: float = 180.0
_PUE: float = 1.2            # Power Usage Effectiveness
_KW_FROM_W: float = 1000.0
_WORKLOAD_HOURS: float = 1.0  # reference window

# ---------------------------------------------------------------------------
# Latency base
# ---------------------------------------------------------------------------
_LATENCY_BASE_MS: float = 5.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_jitter(node_name: str, salt: str) -> float:
	"""Return a stable float in [0, 1] derived from the node name and salt.

	This simulates stable hardware-tier characteristics (e.g. newer CPUs,
	faster network, SSD vs HDD) without any per-run randomness.
	"""
	digest = hashlib.sha256(f"{node_name}:{salt}".encode()).digest()
	return int.from_bytes(digest[:4], "big") / 0xFFFF_FFFF


def _pressure(node: NodeMetrics) -> float:
	"""Combined CPU + memory pressure in [0, 1]."""
	return (node.cpu_usage_pct + node.memory_usage_pct) / 200.0


def _pod_contention(node: NodeMetrics, saturation_pods: int = 20) -> float:
	"""Scheduling contention in [0, 1].  Saturates at *saturation_pods*."""
	return min(node.pod_count / saturation_pods, 1.0)


def _history_for_node(node_name: str, limit: int = 5000) -> list[dict]:
	"""Fetch recent historical metrics rows for a specific node.

	This powers optional DL inference. If no data exists, callers should use
	the deterministic formula fallback.
	"""
	try:
		rows = get_metrics_history(limit=limit)
	except Exception:
		return []
	filtered = [row for row in rows if str(row.get("node_name")) == node_name]
	filtered.sort(key=lambda item: str(item.get("collected_at", "")))
	return filtered


def _dl_prediction(workload: WorkloadRequest, node: NodeMetrics):
	model = load_trained_model()
	if model is None:
		return None
	history = _history_for_node(node.node_name)
	if len(history) < DL_WINDOW:
		return None
	return dl_infer(
		history_window=history,
		workload_features={
			"cpu_cores": workload.cpu_cores,
			"memory_gb": workload.memory_gb,
			"gpu_units": float(workload.gpu_units or 0.0),
			"priority": workload.priority,
		},
		model=model,
	)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_feature_vector(workload: WorkloadRequest, node: NodeMetrics) -> list[float]:
	"""Return a numeric feature vector suitable for an sklearn estimator."""
	return [
		workload.cpu_cores,
		workload.memory_gb,
		float(workload.gpu_units or 0.0),
		workload.latency_sla_ms / 1_000.0,
		workload.failure_prob_sla,
		float(workload.priority),
		node.cpu_usage_pct / 100.0,
		node.memory_usage_pct / 100.0,
		float(node.pod_count),
		1.0 if node.available else 0.0,
	]


def estimate_cost(workload: WorkloadRequest, node: NodeMetrics) -> float:
	"""Estimate hourly cost (USD) for placing this workload on *node*.

	Higher-utilisation nodes charge a congestion premium (up to +40 %) and
	each node has a stable hardware-tier multiplier derived from its name.
	This ensures distinct cost values even when workload specs are identical.
	"""
	# Base resource cost
	base = (
		workload.cpu_cores * _CPU_COST_USD_PER_CORE_HOUR
		+ workload.memory_gb * _MEM_COST_USD_PER_GB_HOUR
		+ float(workload.gpu_units or 0.0) * _GPU_COST_USD_PER_UNIT_HOUR
	)
	# Congestion premium: busy nodes are more expensive (QoS degradation risk)
	congestion = 1.0 + 0.40 * _pressure(node)
	# Hardware-tier multiplier: 0.82x (budget) → 1.18x (premium tier)
	tier = 0.82 + 0.36 * _node_jitter(node.node_name, "cost")
	return round(base * congestion * tier, 6)


def estimate_energy(workload: WorkloadRequest, node: NodeMetrics) -> float:
	"""Estimate energy consumption (kWh) over one hour.

	Nodes running near capacity have degraded power efficiency (higher energy
	per workload unit).  A node-specific efficiency class adds further spread.
	"""
	base_w = (
		workload.cpu_cores * _CPU_WATTS_PER_CORE
		+ workload.memory_gb * _MEM_WATTS_PER_GB
		+ float(workload.gpu_units or 0.0) * _GPU_WATTS_PER_UNIT
	)
	# Pressure degrades efficiency: up to +35 % more power at full load
	inefficiency = 1.0 + 0.35 * _pressure(node)
	# Node power-efficiency class: 0.86x (green) → 1.14x (legacy)
	eff_class = 0.86 + 0.28 * _node_jitter(node.node_name, "energy")
	kwh = base_w * inefficiency * eff_class * _PUE / _KW_FROM_W * _WORKLOAD_HOURS
	return round(kwh, 6)


def predict_failure_prob(workload: WorkloadRequest, node: NodeMetrics) -> float:
	"""Predict the probability that this deployment will fail or be evicted.

	Driven by node pressure, pod contention, workload risk tolerance, priority,
	and a stable per-node reliability score (some nodes are inherently less
	stable due to hardware age, flaky network, etc.).
	"""
	dl = _dl_prediction(workload, node)
	if dl is not None:
		return round(min(max(dl.predicted_failure_probability, 0.01), 0.95), 4)

	p = _pressure(node)
	c = _pod_contention(node)

	# Node reliability: 0.70 (unstable) → 1.30 (rock-solid)
	stability = 0.70 + 0.60 * _node_jitter(node.node_name, "failure")

	# Workload risk-tolerance sensitivity
	risk_mod = {"low": 1.30, "medium": 1.00, "high": 0.75}.get(
		workload.risk_tolerance.value
		if hasattr(workload.risk_tolerance, "value")
		else str(workload.risk_tolerance),
		1.0,
	)
	# High-priority workloads get better scheduler attention
	priority_mod = 1.0 - (workload.priority - 1) * 0.05  # 1.0 → 0.80 for p5

	raw = (0.05 + 0.35 * p + 0.15 * c) * stability * risk_mod * priority_mod
	return round(min(max(raw, 0.01), 0.95), 4)


def predict_latency(workload: WorkloadRequest, node: NodeMetrics) -> float:
	"""Estimate p95 request latency (ms) for this workload on *node*.

	Components:
	- Base scheduling/network overhead
	- CPU queuing delay (exponential near saturation)
	- Memory-pressure cache-miss penalty
	- Pod-count scheduling noise
	- Workload size overhead
	- Stable hardware latency characteristics (NIC speed, disk, NUMA, etc.)
	"""
	dl = _dl_prediction(workload, node)
	if dl is not None:
		return round(max(dl.predicted_latency_ms, 1.0), 3)

	cpu_ratio = node.cpu_usage_pct / 100.0
	# Exponential queuing delay: gentle at low load, steep above 70 %
	queuing_ms = (math.exp(1.8 * cpu_ratio) - 1.0) * 25.0
	# Memory pressure causes cache misses → extra latency
	mem_ms = node.memory_usage_pct * 0.45
	# Pod scheduling noise
	pod_ms = node.pod_count * 1.5
	# Workload compute weight
	workload_ms = workload.cpu_cores * 3.0 + workload.memory_gb * 1.0
	# Hardware offset: 2 ms (fast NVMe, 25 GbE) → 16 ms (legacy HDD, 1 GbE)
	hw_ms = 2.0 + 14.0 * _node_jitter(node.node_name, "latency")

	return round(_LATENCY_BASE_MS + queuing_ms + mem_ms + pod_ms + workload_ms + hw_ms, 3)


def predict_resource_demand(workload: WorkloadRequest, node: NodeMetrics) -> float:
	"""Predict normalized future resource demand for this workload/node.

	Returns value in [0, 2], where 1 is nominal expected demand.
	"""
	dl = _dl_prediction(workload, node)
	if dl is not None:
		return round(min(max(dl.predicted_resource_demand, 0.0), 2.0), 4)

	# Formula fallback proxy: workload demand + current node pressure.
	base = (workload.cpu_cores / 4.0) + (workload.memory_gb / 8.0) + (float(workload.gpu_units or 0.0) * 0.3)
	pressure = _pressure(node)
	return round(min(max(base * (1.0 + pressure), 0.0), 2.0), 4)


def load_latency_model() -> Any:
	"""Load a pre-trained joblib latency model if one exists, else return None."""
	model_path = Path(__file__).resolve().parent / "latency_model.pkl"
	if not model_path.exists():
		return None
	try:
		import joblib  # type: ignore[import]
		return joblib.load(model_path)
	except Exception:
		return None


def predict_latency_ml(features: list[float], model: Any) -> float:
	"""Use a trained sklearn model to predict latency.  Falls back to 50 ms."""
	try:
		import numpy as np  # type: ignore[import]
		prediction = model.predict(np.array(features).reshape(1, -1))
		return float(max(prediction[0], 1.0))
	except Exception:
		return 50.0
