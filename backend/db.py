"""Supabase client and persistence helpers for the compute allocator backend."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from supabase import Client, create_client

from backend.models import AgentScore, DecisionResult, DeploymentScenario, NodeMetrics, WorkloadRequest

BASE_DIR = Path(__file__).resolve().parent
load_dotenv()
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env", override=False)

supabase: Client | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _audit_prev_hash(workload_id: str) -> str | None:
    try:
        response = (
            get_supabase()
            .table("audit_events")
            .select("event_hash")
            .eq("workload_id", workload_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0].get("event_hash") if rows else None
    except Exception:
        return None


def insert_audit_event(workload_id: str, action: str, payload: Any) -> None:
    """Insert a tamper-evident audit record.

    If the `audit_events` table is absent, this function fails silently so that
    existing flows are not interrupted.
    """
    try:
        created_at = _utc_now_iso()
        previous_hash = _audit_prev_hash(workload_id)
        payload_json = _stable_json(payload)
        hash_input = f"{workload_id}|{action}|{created_at}|{previous_hash or ''}|{payload_json}"
        event_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        event_payload = {
            "workload_id": workload_id,
            "action": action,
            "payload": payload,
            "payload_json": payload_json,
            "previous_hash": previous_hash,
            "event_hash": event_hash,
            "created_at": created_at,
        }
        get_supabase().table("audit_events").insert(event_payload).execute()
    except Exception:
        # Optional capability: keep core data path resilient even if audit table
        # is not yet created or temporarily unavailable.
        return


def get_supabase() -> Client:
    global supabase

    if supabase is not None:
        return supabase

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY. "
            "Create backend/.env from .env.example before running the backend."
        )

    supabase = create_client(url, key)
    return supabase


try:
    supabase = get_supabase()
except RuntimeError:
    # The backend can still be imported before environment variables are configured.
    supabase = None


def _workload_payload(workload: WorkloadRequest) -> dict[str, Any]:
    return {
        "workload_id": workload.workload_id,
        "name": workload.name,
        "container_image": workload.container_image,
        "cpu_cores": workload.cpu_cores,
        "gpu_units": workload.gpu_units,
        "memory_gb": workload.memory_gb,
        "latency_sla_ms": workload.latency_sla_ms,
        "failure_prob_sla": workload.failure_prob_sla,
        "risk_tolerance": workload.risk_tolerance.value,
        "budget_usd": workload.budget_usd,
        "energy_preference": workload.energy_preference.value,
        "priority": workload.priority,
        "submitted_at": workload.submitted_at,
        "status": workload.status.value,
    }


def _scenario_payload(scenario: DeploymentScenario) -> dict[str, Any]:
    return {
        "scenario_id": scenario.scenario_id,
        "workload_id": scenario.workload_id,
        "target_node": scenario.target_node,
        "predicted_latency_ms": scenario.predicted_latency_ms,
        "predicted_failure_prob": scenario.predicted_failure_prob,
        "estimated_cost_usd": scenario.estimated_cost_usd,
        "estimated_energy_kwh": scenario.estimated_energy_kwh,
    }


def _score_payload(score: AgentScore) -> dict[str, Any]:
    return {
        "scenario_id": score.scenario_id,
        "workload_id": score.workload_id,
        "agent_name": score.agent_name.value,
        "raw_score": score.raw_score,
        "reasoning": score.reasoning,
    }


def _decision_payload(result: DecisionResult) -> dict[str, Any]:
    return {
        "workload_id": result.workload_id,
        "selected_scenario_id": result.selected_scenario_id,
        "final_scores": result.final_scores,
        "decision_reasoning": result.decision_reasoning,
        "decided_at": result.decided_at or _utc_now_iso(),
    }


def _metrics_payload(node: NodeMetrics) -> dict[str, Any]:
    return {
        "node_name": node.node_name,
        "cpu_usage_pct": node.cpu_usage_pct,
        "memory_usage_pct": node.memory_usage_pct,
        "gpu_usage_pct": node.gpu_usage_pct,
        "pod_count": node.pod_count,
        "available": node.available,
        "collected_at": node.collected_at,
    }


def insert_workload(workload: WorkloadRequest) -> dict[str, Any]:
    payload = _workload_payload(workload)
    response = get_supabase().table("workloads").insert(payload).execute()
    rows = response.data or []
    created = rows[0] if rows else payload
    insert_audit_event(workload.workload_id, "workload.created", created)
    return created


def get_workload(workload_id: str) -> dict[str, Any] | None:
    try:
        response = (
            get_supabase()
            .table("workloads")
            .select("*")
            .eq("workload_id", workload_id)
            .single()
            .execute()
        )
    except Exception:
        return None
    rows = response.data or {}
    return rows or None


def update_workload_status(workload_id: str, status: str) -> None:
    get_supabase().table("workloads").update({"status": status}).eq("workload_id", workload_id).execute()
    insert_audit_event(workload_id, "workload.status_updated", {"status": status})


def insert_scenarios(scenarios: list[DeploymentScenario]) -> list[dict[str, Any]]:
    if not scenarios:
        return []

    payload = [_scenario_payload(scenario) for scenario in scenarios]
    response = get_supabase().table("deployment_scenarios").insert(payload).execute()
    rows = response.data or payload
    insert_audit_event(scenarios[0].workload_id, "scenarios.generated", {"count": len(rows), "scenarios": rows})
    return rows


def insert_agent_scores(scores: list[AgentScore]) -> list[dict[str, Any]]:
    if not scores:
        return []

    payload = [_score_payload(score) for score in scores]
    response = get_supabase().table("agent_scores").insert(payload).execute()
    rows = response.data or payload
    insert_audit_event(scores[0].workload_id, "agents.scored", {"count": len(rows)})
    return rows


def insert_decision(result: DecisionResult) -> None:
    payload = _decision_payload(result)
    get_supabase().table("decision_results").upsert(payload).execute()
    insert_audit_event(result.workload_id, "decision.selected", payload)


def get_decision(workload_id: str) -> dict[str, Any] | None:
    try:
        decision_response = (
            get_supabase()
            .table("decision_results")
            .select("*")
            .eq("workload_id", workload_id)
            .single()
            .execute()
        )
    except Exception:
        return None

    scenarios_response = (
        get_supabase()
        .table("deployment_scenarios")
        .select("*")
        .eq("workload_id", workload_id)
        .order("estimated_cost_usd")
        .execute()
    )
    scores_response = (
        get_supabase()
        .table("agent_scores")
        .select("*")
        .eq("workload_id", workload_id)
        .order("id")
        .execute()
    )

    decision = dict(decision_response.data or {})
    decision["all_scenarios"] = scenarios_response.data or []
    decision["agent_scores"] = scores_response.data or []
    return decision


def insert_log(workload_id: str, message: str, level: str) -> None:
    payload = {
        "workload_id": workload_id,
        "message": message,
        "level": level,
        "created_at": _utc_now_iso(),
    }
    get_supabase().table("log_entries").insert(payload).execute()
    insert_audit_event(workload_id, "log.appended", payload)


def get_logs(workload_id: str, limit: int = 50) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("log_entries")
        .select("*")
        .eq("workload_id", workload_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def insert_metrics_snapshot(node: NodeMetrics) -> None:
    payload = _metrics_payload(node)
    get_supabase().table("node_metrics_snapshots").insert(payload).execute()


def get_audit_events(workload_id: str, limit: int = 200) -> list[dict[str, Any]]:
    try:
        response = (
            get_supabase()
            .table("audit_events")
            .select("*")
            .eq("workload_id", workload_id)
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def verify_audit_chain(workload_id: str, limit: int = 200) -> dict[str, Any]:
    events = get_audit_events(workload_id, limit=limit)
    if not events:
        return {
            "workload_id": workload_id,
            "ok": False,
            "checked_events": 0,
            "reason": "No audit events found (or audit table unavailable).",
        }

    previous_hash: str | None = None
    for event in events:
        payload_json = event.get("payload_json") or _stable_json(event.get("payload"))
        expected_input = (
            f"{event.get('workload_id')}|{event.get('action')}|{event.get('created_at')}|"
            f"{previous_hash or ''}|{payload_json}"
        )
        expected_hash = hashlib.sha256(expected_input.encode("utf-8")).hexdigest()
        if event.get("event_hash") != expected_hash or event.get("previous_hash") != previous_hash:
            return {
                "workload_id": workload_id,
                "ok": False,
                "checked_events": len(events),
                "failed_event_id": event.get("id"),
                "failed_action": event.get("action"),
                "reason": "Audit chain mismatch detected.",
            }
        previous_hash = event.get("event_hash")

    return {
        "workload_id": workload_id,
        "ok": True,
        "checked_events": len(events),
        "last_hash": previous_hash,
    }


def get_metrics_history(limit: int = 500) -> list[dict[str, Any]]:
    response = (
        get_supabase()
        .table("node_metrics_snapshots")
        .select("*")
        .order("collected_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def save_deployment_state(
    workload_id: str,
    *,
    target: str,
    mode: str,
    state: str,
    message: str,
    run_url: str | None = None,
    workflow_url: str | None = None,
    error_message: str | None = None,
    run_id: str | None = None,
    new_run: bool = False,
) -> dict[str, Any] | None:
    """Persist deployment state snapshots.

    Returns the saved row (or payload fallback) when successful.
    Returns None if table is unavailable.
    """
    try:
        now = _utc_now_iso()
        db = get_supabase().table("deployment_runs")

        if new_run or not run_id:
            next_run_id = str(uuid4())
            payload = {
                "run_id": next_run_id,
                "workload_id": workload_id,
                "target": target,
                "mode": mode,
                "state": state,
                "message": message,
                "workflow_url": workflow_url,
                "run_url": run_url,
                "error_message": error_message,
                "created_at": now,
                "updated_at": now,
            }
            response = db.insert(payload).execute()
            rows = response.data or []
            return rows[0] if rows else payload

        payload = {
            "target": target,
            "mode": mode,
            "state": state,
            "message": message,
            "workflow_url": workflow_url,
            "run_url": run_url,
            "error_message": error_message,
            "updated_at": now,
        }
        response = db.update(payload).eq("run_id", run_id).execute()
        rows = response.data or []
        if rows:
            return rows[0]

        # If run_id does not exist, create a new row to keep state durable.
        return save_deployment_state(
            workload_id,
            target=target,
            mode=mode,
            state=state,
            message=message,
            run_url=run_url,
            workflow_url=workflow_url,
            error_message=error_message,
            run_id=None,
            new_run=True,
        )
    except Exception:
        return None


def get_latest_deployment_state(workload_id: str) -> dict[str, Any] | None:
    try:
        response = (
            get_supabase()
            .table("deployment_runs")
            .select("*")
            .eq("workload_id", workload_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None
    except Exception:
        return None
