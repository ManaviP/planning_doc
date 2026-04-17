"""Prometheus-backed node metrics collection with a synthetic fallback."""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any

from prometheus_api_client import PrometheusConnect

from backend.db import insert_metrics_snapshot
from backend.models import NodeMetrics

LOGGER = logging.getLogger(__name__)
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
REFRESH_INTERVAL_SECONDS = 15
SYNTHETIC_NODE_COUNT = max(1, int(os.getenv("SYNTHETIC_NODE_COUNT", "3")))

_CPU_QUERY = """
100 - (avg by (node) (rate(
  node_cpu_seconds_total{mode=\"idle\"}[2m]
)) * 100)
""".strip()

_MEMORY_QUERY = """
100 - (node_memory_MemAvailable_bytes /
       node_memory_MemTotal_bytes * 100)
""".strip()

_POD_COUNT_QUERY = "count by (node) (kube_pod_info{node!=\"\"})"
_AVAILABILITY_QUERY = 'kube_node_status_condition{condition="Ready",status="true"}'

_cache_lock = threading.Lock()
_latest_metrics: list[NodeMetrics] = []
_last_refresh_epoch = 0.0
_refresh_thread: threading.Thread | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_node_name(result: dict[str, Any]) -> str:
    metric = result.get("metric", {})
    return (
        metric.get("node")
        or metric.get("kubernetes_node")
        or metric.get("nodename")
        or (metric.get("instance", "unknown-node").split(":")[0])
    )


def _extract_float(result: dict[str, Any], default: float = 0.0) -> float:
    value = result.get("value")
    if isinstance(value, list) and len(value) >= 2:
        try:
            return float(value[1])
        except (TypeError, ValueError):
            return default
    return default


def _get_prometheus_client() -> PrometheusConnect:
    return PrometheusConnect(url=PROMETHEUS_URL, disable_ssl=True)


def _query_map(client: PrometheusConnect, query: str) -> dict[str, float]:
    results = client.custom_query(query=query)
    return {_extract_node_name(item): _extract_float(item) for item in results}


def _query_availability(client: PrometheusConnect) -> dict[str, bool]:
    results = client.custom_query(query=_AVAILABILITY_QUERY)
    availability: dict[str, bool] = {}
    for item in results:
        availability[_extract_node_name(item)] = _extract_float(item, default=0.0) >= 1.0
    return availability


def _persist_snapshots(nodes: list[NodeMetrics]) -> None:
    for node in nodes:
        try:
            insert_metrics_snapshot(node)
        except Exception as exc:  # pragma: no cover - external dependency failure
            LOGGER.warning("Failed to persist metrics snapshot for %s: %s", node.node_name, exc)


def _synthetic_metrics() -> list[NodeMetrics]:
    timestamp = _utc_now_iso()
    synthetic_nodes: list[NodeMetrics] = []
    for index in range(SYNTHETIC_NODE_COUNT):
        node_number = index + 1
        synthetic_nodes.append(
            NodeMetrics(
                node_name=f"minikube-m{node_number:02d}",
                cpu_usage_pct=round(min(92.0, 30.0 + (index * 11.5) + random.uniform(-4.0, 5.5)), 1),
                memory_usage_pct=round(min(90.0, 45.0 + (index * 8.7) + random.uniform(-4.5, 5.0)), 1),
                gpu_usage_pct=None,
                pod_count=max(1, 6 + index * 2 + random.randint(-2, 2)),
                available=True if index < 2 else bool(random.choice([True, True, True, False])),
                collected_at=timestamp,
            )
        )
    _persist_snapshots(synthetic_nodes)
    return synthetic_nodes


def collect_node_metrics() -> list[NodeMetrics]:
    try:
        client = _get_prometheus_client()
        cpu_usage = _query_map(client, _CPU_QUERY)
        memory_usage = _query_map(client, _MEMORY_QUERY)
        pod_counts = _query_map(client, _POD_COUNT_QUERY)
        availability = _query_availability(client)

        all_nodes = set(cpu_usage) | set(memory_usage) | set(pod_counts) | set(availability)
        if not all_nodes:
            raise RuntimeError("Prometheus returned no node metrics")

        timestamp = _utc_now_iso()
        metrics = [
            NodeMetrics(
                node_name=node_name,
                cpu_usage_pct=round(cpu_usage.get(node_name, 0.0), 3),
                memory_usage_pct=round(memory_usage.get(node_name, 0.0), 3),
                gpu_usage_pct=None,
                pod_count=int(round(pod_counts.get(node_name, 0.0))),
                available=availability.get(node_name, False),
                collected_at=timestamp,
            )
            for node_name in sorted(all_nodes)
        ]
        _persist_snapshots(metrics)
        return metrics
    except Exception as exc:  # pragma: no cover - external dependency failure
        LOGGER.warning("Prometheus is unreachable or incomplete, using synthetic metrics: %s", exc)
        return _synthetic_metrics()


def _refresh_metrics_forever(interval_seconds: int) -> None:
    global _latest_metrics, _last_refresh_epoch

    while True:
        metrics = collect_node_metrics()
        with _cache_lock:
            _latest_metrics = metrics
            _last_refresh_epoch = time.time()
        time.sleep(interval_seconds)


def start_metrics_collector(interval_seconds: int = REFRESH_INTERVAL_SECONDS) -> None:
    global _refresh_thread

    if _refresh_thread and _refresh_thread.is_alive():
        return

    _refresh_thread = threading.Thread(
        target=_refresh_metrics_forever,
        args=(interval_seconds,),
        name="node-metrics-collector",
        daemon=True,
    )
    _refresh_thread.start()


def get_latest_metrics() -> list[NodeMetrics]:
    """Return metrics quickly for API consumers.

    Request handlers should never block on Prometheus latency. The background
    collector keeps cache fresh; here we serve cached data immediately and fall
    back to synthetic metrics if cache is not ready yet.
    """
    with _cache_lock:
        cached = list(_latest_metrics)

    if cached:
        return cached

    # Cold-start fallback: do not block request path on network I/O.
    return _synthetic_metrics()


start_metrics_collector()
