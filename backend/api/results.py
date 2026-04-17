"""Result and log read APIs."""

from __future__ import annotations

import logging
from dataclasses import asdict
from fastapi import APIRouter, HTTPException, Query, status

from backend.db import (
    get_audit_events,
    get_decision,
    get_logs,
    get_metrics_history,
    get_supabase,
    get_workload,
    verify_audit_chain,
)
from backend.models import EnergyPreference, NodeMetrics, RiskTolerance, WorkloadRequest, WorkloadStatus
from backend.prediction.engine import predict_failure_prob, predict_latency, predict_resource_demand
from backend.simulation.monte_carlo import run_monte_carlo

router = APIRouter(prefix="/results", tags=["results"])
LOGGER = logging.getLogger(__name__)


def _workload_from_record(record: dict) -> WorkloadRequest:
    return WorkloadRequest(
        workload_id=str(record["workload_id"]),
        name=str(record["name"]),
        container_image=str(record["container_image"]),
        cpu_cores=float(record["cpu_cores"]),
        gpu_units=None if record.get("gpu_units") is None else float(record["gpu_units"]),
        memory_gb=float(record["memory_gb"]),
        latency_sla_ms=int(record["latency_sla_ms"]),
        failure_prob_sla=float(record["failure_prob_sla"]),
        risk_tolerance=RiskTolerance(str(record["risk_tolerance"])),
        budget_usd=None if record.get("budget_usd") is None else float(record["budget_usd"]),
        energy_preference=EnergyPreference(str(record["energy_preference"])),
        priority=int(record["priority"]),
        submitted_at=str(record.get("submitted_at")),
        status=WorkloadStatus(str(record.get("status", WorkloadStatus.PENDING.value))),
    )


def _latest_node_snapshot(node_name: str) -> NodeMetrics | None:
    rows = get_metrics_history(limit=1000)
    for row in rows:
        if str(row.get("node_name")) != node_name:
            continue
        return NodeMetrics(
            node_name=str(row["node_name"]),
            cpu_usage_pct=float(row.get("cpu_usage_pct") or 0.0),
            memory_usage_pct=float(row.get("memory_usage_pct") or 0.0),
            gpu_usage_pct=None if row.get("gpu_usage_pct") is None else float(row.get("gpu_usage_pct")),
            pod_count=int(row.get("pod_count") or 0),
            available=bool(row.get("available", True)),
            collected_at=str(row.get("collected_at", "")),
        )
    return None


def _selected_scenario(decision: dict) -> dict | None:
    selected_id = decision.get("selected_scenario_id")
    for scenario in decision.get("all_scenarios", []):
        if scenario.get("scenario_id") == selected_id:
            return scenario
    return None


def _build_reasoning_structured(
    workload_payload: dict | None,
    decision_payload: dict | None,
    scenarios: list[dict],
) -> dict:
    if not decision_payload:
        return {
            "summary": "Decision reasoning is not available yet.",
            "why_this_node_won": [],
            "tradeoffs": [],
        }

    selected_id = decision_payload.get("selected_scenario_id")
    selected = next((item for item in scenarios if item.get("scenario_id") == selected_id), None)
    if not selected:
        return {
            "summary": "Selected scenario details are not available yet.",
            "why_this_node_won": [],
            "tradeoffs": [],
        }

    selected_latency = float(selected.get("predicted_latency_ms") or 0.0)
    selected_failure = float(selected.get("predicted_failure_prob") or 0.0)
    selected_cost = float(selected.get("estimated_cost_usd") or 0.0)
    selected_energy = float(selected.get("estimated_energy_kwh") or 0.0)

    if scenarios:
        avg_latency = sum(float(item.get("predicted_latency_ms") or 0.0) for item in scenarios) / len(scenarios)
        avg_failure = sum(float(item.get("predicted_failure_prob") or 0.0) for item in scenarios) / len(scenarios)
        avg_cost = sum(float(item.get("estimated_cost_usd") or 0.0) for item in scenarios) / len(scenarios)
        avg_energy = sum(float(item.get("estimated_energy_kwh") or 0.0) for item in scenarios) / len(scenarios)
    else:
        avg_latency = selected_latency
        avg_failure = selected_failure
        avg_cost = selected_cost
        avg_energy = selected_energy

    def _delta(reference: float, candidate: float, multiplier: float = 1.0) -> str:
        gap = (reference - candidate) * multiplier
        sign = "+" if gap >= 0 else ""
        return f"{sign}{gap:.2f}"

    why_lines = [
        (
            f"Latency: {selected_latency:.2f} ms "
            f"(vs average {avg_latency:.2f} ms, delta {_delta(avg_latency, selected_latency)} ms)."
        ),
        (
            f"Failure probability: {selected_failure * 100:.2f}% "
            f"(vs average {avg_failure * 100:.2f}%, delta {_delta(avg_failure, selected_failure, 100)} pp)."
        ),
        (
            f"Estimated cost: ${selected_cost:.4f} "
            f"(vs average ${avg_cost:.4f}, delta {_delta(avg_cost, selected_cost)})."
        ),
        (
            f"Estimated energy: {selected_energy:.4f} kWh "
            f"(vs average {avg_energy:.4f} kWh, delta {_delta(avg_energy, selected_energy)})."
        ),
    ]

    tradeoffs: list[str] = []
    budget = None
    latency_sla = None
    risk_sla = None
    if workload_payload:
        budget = workload_payload.get("budget_usd")
        latency_sla = workload_payload.get("latency_sla_ms")
        risk_sla = workload_payload.get("failure_prob_sla")

    if budget is not None:
        budget_value = float(budget)
        if selected_cost <= budget_value:
            tradeoffs.append(f"Within budget (${selected_cost:.4f} <= ${budget_value:.4f}).")
        else:
            tradeoffs.append(f"Above budget by ${selected_cost - budget_value:.4f}.")

    if latency_sla is not None:
        latency_limit = float(latency_sla)
        if selected_latency <= latency_limit:
            tradeoffs.append(f"Meets latency SLA ({selected_latency:.2f} ms <= {latency_limit:.2f} ms).")
        else:
            tradeoffs.append(f"Exceeds latency SLA by {selected_latency - latency_limit:.2f} ms.")

    if risk_sla is not None:
        risk_limit = float(risk_sla)
        if selected_failure <= risk_limit:
            tradeoffs.append(f"Meets failure SLA ({selected_failure * 100:.2f}% <= {risk_limit * 100:.2f}%).")
        else:
            tradeoffs.append(f"Exceeds failure SLA by {(selected_failure - risk_limit) * 100:.2f} pp.")

    summary = (
        f"Node {selected.get('target_node', 'unknown')} selected for scenario {selected.get('scenario_id', 'n/a')} "
        "based on weighted multi-agent scoring."
    )
    return {
        "summary": summary,
        "why_this_node_won": why_lines,
        "tradeoffs": tradeoffs,
    }


@router.get("/{workload_id}")
def read_result(workload_id: str) -> dict:
    workload = get_workload(workload_id)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found.")

    decision = get_decision(workload_id)
    return {"workload": workload, "decision": decision}


@router.get("/{workload_id}/logs")
def read_logs(workload_id: str, limit: int = Query(default=50, ge=1, le=500)) -> list[dict]:
    workload = get_workload(workload_id)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found.")

    return get_logs(workload_id, limit=limit)


@router.get("/{workload_id}/audit")
def read_audit_events(workload_id: str, limit: int = Query(default=200, ge=1, le=1000)) -> list[dict]:
    workload = get_workload(workload_id)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found.")

    return get_audit_events(workload_id, limit=limit)


@router.get("/{workload_id}/audit/verify")
def read_audit_verification(workload_id: str, limit: int = Query(default=200, ge=1, le=1000)) -> dict:
    workload = get_workload(workload_id)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found.")

    return verify_audit_chain(workload_id, limit=limit)


@router.get("/{workload_id}/simulation")
def read_simulation(workload_id: str, iterations: int = Query(default=300, ge=20, le=5000)) -> dict:
    workload = get_workload(workload_id)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found.")

    decision = get_decision(workload_id)
    if decision is None:
        return {
            "workload_id": workload_id,
            "available": False,
            "reason": "Decision not found for workload yet.",
            "iterations": iterations,
            "distribution": [],
            "stats": None,
        }

    scenario = _selected_scenario(decision)
    if scenario is None:
        return {
            "workload_id": workload_id,
            "available": False,
            "reason": "Selected scenario details not found yet.",
            "iterations": iterations,
            "distribution": [],
            "stats": None,
        }

    node = _latest_node_snapshot(str(scenario.get("target_node")))
    if node is None:
        return {
            "workload_id": workload_id,
            "available": False,
            "reason": "Node metrics unavailable for simulation.",
            "iterations": iterations,
            "selected_scenario_id": str(scenario.get("scenario_id")),
            "node": str(scenario.get("target_node")),
            "distribution": [],
            "stats": None,
        }

    wl = _workload_from_record(workload)
    simulation = run_monte_carlo(wl, node, iterations=iterations)

    return {
        "workload_id": workload_id,
        "available": True,
        "selected_scenario_id": str(scenario.get("scenario_id")),
        "node": node.node_name,
        "base_node_snapshot": asdict(node),
        "simulation": asdict(simulation),
        "distribution": [],
        "stats": {
            "latency_ms_mean": round(float(simulation.latency_ms_mean), 4),
            "latency_ms_p95": round(float(simulation.latency_ms_p95), 4),
            "failure_prob_mean": round(float(simulation.failure_prob_mean), 6),
            "failure_prob_p95": round(float(simulation.failure_prob_p95), 6),
            "demand_mean": round(float(simulation.demand_mean), 6),
            "sla_breach_rate": round(float(simulation.sla_breach_rate), 6),
            "iterations": int(simulation.iterations),
        },
    }


@router.get("/{workload_id}/evaluation")
def read_prediction_evaluation(workload_id: str) -> dict:
    workload = get_workload(workload_id)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found.")

    decision = get_decision(workload_id)
    if decision is None:
        return {
            "workload_id": workload_id,
            "available": False,
            "reason": "Decision not found for workload yet.",
        }

    scenario = _selected_scenario(decision)
    if scenario is None:
        return {
            "workload_id": workload_id,
            "available": False,
            "reason": "Selected scenario details not found yet.",
        }

    node = _latest_node_snapshot(str(scenario.get("target_node")))
    if node is None:
        return {
            "workload_id": workload_id,
            "available": False,
            "reason": "Node metrics unavailable for evaluation.",
            "selected_scenario_id": str(scenario.get("scenario_id")),
            "node": str(scenario.get("target_node")),
        }

    wl = _workload_from_record(workload)

    predicted_latency = float(scenario.get("predicted_latency_ms") or 0.0)
    predicted_failure = float(scenario.get("predicted_failure_prob") or 0.0)

    actual_latency = float(predict_latency(wl, node))
    # observed failure is binary based on status when terminal; fallback to model estimate
    status_value = str(workload.get("status", ""))
    if status_value == WorkloadStatus.FAILED.value:
        actual_failure = 1.0
    elif status_value == WorkloadStatus.DEPLOYED.value:
        actual_failure = 0.0
    else:
        actual_failure = float(predict_failure_prob(wl, node))

    predicted_demand = float(predict_resource_demand(wl, node))
    actual_demand = min(max((node.cpu_usage_pct + node.memory_usage_pct) / 200.0, 0.0), 2.0)

    latency_abs_error = abs(actual_latency - predicted_latency)
    failure_abs_error = abs(actual_failure - predicted_failure)
    demand_abs_error = abs(actual_demand - predicted_demand)

    latency_accuracy = max(0.0, 1.0 - latency_abs_error / max(predicted_latency, 1.0))
    failure_accuracy = max(0.0, 1.0 - failure_abs_error)
    demand_accuracy = max(0.0, 1.0 - demand_abs_error / max(predicted_demand, 0.1))

    overall_accuracy = (latency_accuracy + failure_accuracy + demand_accuracy) / 3.0

    return {
        "workload_id": workload_id,
        "available": True,
        "selected_scenario_id": str(scenario.get("scenario_id")),
        "node": node.node_name,
        "predicted": {
            "latency_ms": round(predicted_latency, 4),
            "failure_probability": round(predicted_failure, 6),
            "resource_demand": round(predicted_demand, 6),
        },
        "actual": {
            "latency_ms": round(actual_latency, 4),
            "failure_probability": round(actual_failure, 6),
            "resource_demand": round(actual_demand, 6),
        },
        "errors": {
            "latency_abs_error": round(latency_abs_error, 6),
            "failure_abs_error": round(failure_abs_error, 6),
            "resource_demand_abs_error": round(demand_abs_error, 6),
        },
        "accuracy": {
            "latency_accuracy": round(latency_accuracy, 6),
            "failure_accuracy": round(failure_accuracy, 6),
            "resource_demand_accuracy": round(demand_accuracy, 6),
            "overall_accuracy": round(overall_accuracy, 6),
        },
    }


@router.get("/{workload_id}/decision-panel")
def get_decision_panel_data(workload_id: str):
    """Fetch all data needed for decision panel (workload, decision, scenarios, scores).
    
    Used by frontend to avoid direct Supabase calls which fail due to CORS.
    """
    workload_record = get_workload(workload_id)
    if not workload_record:
        raise HTTPException(status_code=404, detail="Workload not found")

    decision_record = get_decision(workload_id)

    scenarios: list[dict] = []
    scores: list[dict] = []
    try:
        db = get_supabase()
        scenarios = db.table("deployment_scenarios").select("*").eq("workload_id", workload_id).execute().data or []
        scores = db.table("agent_scores").select("*").eq("workload_id", workload_id).execute().data or []
    except Exception as exc:
        LOGGER.warning("Decision panel supplemental data unavailable for %s: %s", workload_id, exc)

    try:
        workload_payload = asdict(_workload_from_record(workload_record))
    except Exception as exc:
        LOGGER.warning("Decision panel workload normalization failed for %s: %s", workload_id, exc)
        workload_payload = workload_record

    try:
        decision_payload = (asdict(decision_record) if hasattr(decision_record, "__dataclass_fields__") else decision_record) if decision_record else None
    except Exception as exc:
        LOGGER.warning("Decision panel decision normalization failed for %s: %s", workload_id, exc)
        decision_payload = decision_record if isinstance(decision_record, dict) else None

    if isinstance(decision_payload, dict):
        decision_payload = {
            **decision_payload,
            "reasoning_structured": _build_reasoning_structured(workload_payload, decision_payload, scenarios),
        }

    return {
        "workload": workload_payload,
        "decision": decision_payload,
        "scenarios": scenarios,
        "scores": scores,
    }


@router.get("/stats/active-workloads")
def get_active_workloads_count():
    """Get count of active workloads (evaluating or deployed)."""
    try:
        db = get_supabase()
        result = db.table("workloads").select("workload_id", count="exact").in_("status", ["evaluating", "deployed"]).execute()
        return {"count": result.count or 0}
    except Exception as exc:
        LOGGER.warning("Active workloads count unavailable: %s", exc)
        return {"count": 0}
