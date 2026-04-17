
"""Workload submission and orchestration APIs."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field, ValidationError, field_validator
import yaml

from backend.db import (
    get_decision,
    get_latest_deployment_state,
    get_supabase,
    get_workload,
    insert_log,
    insert_workload,
    save_deployment_state,
    update_workload_status,
)
from backend.deployment.manager import DeploymentError, DeploymentManager
from backend.metrics.collector import collect_node_metrics, get_latest_metrics
from backend.models import (
    DeploymentScenario,
    EnergyPreference,
    NodeMetrics,
    RiskTolerance,
    WebSocketEvent,
    WebSocketEventType,
    WorkloadRequest,
    WorkloadStatus,
)
from backend.negotiation.engine import NegotiationEngine
from backend.scenarios.generator import NoViableNodeError, generate_scenarios
from backend.websocket.broadcaster import emit_event_sync

LOGGER = logging.getLogger(__name__)
router = APIRouter(tags=["workloads"])
_DEPLOYMENT_STATE: dict[str, dict] = {}


class WorkloadRequestBody(BaseModel):
    workload_id: str | None = None
    name: str = Field(min_length=1)
    container_image: str = Field(min_length=1)
    cpu_cores: float = Field(gt=0)
    gpu_units: float | None = Field(default=None, ge=0)
    memory_gb: float = Field(gt=0)
    latency_sla_ms: int = Field(gt=0)
    failure_prob_sla: float = Field(ge=0, le=1)
    risk_tolerance: RiskTolerance
    budget_usd: float | None = Field(default=None, ge=0)
    energy_preference: EnergyPreference
    priority: int = Field(ge=1, le=5)
    submitted_at: str | None = None
    status: WorkloadStatus | None = None

    @field_validator("name", "container_image")
    @classmethod
    def validate_trimmed_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be empty.")
        return normalized


class WorkloadCreateResponse(BaseModel):
    workload_id: str
    status: WorkloadStatus


class CompetitionRequest(BaseModel):
    workload_a: WorkloadRequestBody
    workload_b: WorkloadRequestBody


class WorkloadYamlRequest(BaseModel):
    yaml_spec: str = Field(min_length=1)


class CompetitionYamlRequest(BaseModel):
    yaml_spec: str = Field(min_length=1)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(event_type: WebSocketEventType, workload_id: str, payload: dict) -> None:
    emit_event_sync(
        WebSocketEvent(
            event_type=event_type,
            workload_id=workload_id,
            payload=payload,
            timestamp=_utc_now_iso(),
        )
    )


def _to_workload_request(payload: WorkloadRequestBody) -> WorkloadRequest:
    return WorkloadRequest(
        workload_id=str(uuid4()),
        name=payload.name,
        container_image=payload.container_image,
        cpu_cores=payload.cpu_cores,
        gpu_units=payload.gpu_units,
        memory_gb=payload.memory_gb,
        latency_sla_ms=payload.latency_sla_ms,
        failure_prob_sla=payload.failure_prob_sla,
        risk_tolerance=payload.risk_tolerance,
        budget_usd=payload.budget_usd,
        energy_preference=payload.energy_preference,
        priority=payload.priority,
        submitted_at=_utc_now_iso(),
        status=WorkloadStatus.PENDING,
    )


def _set_deployment_state(
    workload_id: str,
    *,
    state: str,
    target: str,
    message: str,
    mode: str,
    run_url: str | None = None,
    workflow_url: str | None = None,
    run_id: str | None = None,
    new_run: bool = False,
) -> dict:
    previous = _DEPLOYMENT_STATE.get(workload_id) or {}
    effective_run_id = None if new_run else (run_id or previous.get("run_id"))

    snapshot = {
        "workload_id": workload_id,
        "state": state,
        "target": target,
        "mode": mode,
        "message": message,
        "workflow_url": workflow_url,
        "run_url": run_url,
        "run_id": effective_run_id,
        "updated_at": _utc_now_iso(),
    }

    persisted = save_deployment_state(
        workload_id,
        target=target,
        mode=mode,
        state=state,
        message=message,
        workflow_url=workflow_url,
        run_url=run_url,
        error_message=message if state == "failed" else None,
        run_id=effective_run_id,
        new_run=new_run,
    )
    if persisted:
        snapshot["run_id"] = persisted.get("run_id")
        snapshot["workflow_url"] = persisted.get("workflow_url")
        snapshot["run_url"] = persisted.get("run_url")
        snapshot["updated_at"] = str(persisted.get("updated_at") or snapshot["updated_at"])

    _DEPLOYMENT_STATE[workload_id] = snapshot
    return snapshot


def _trigger_github_actions_dispatch(workload_id: str, target: str) -> dict:
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    workflow = os.getenv("GITHUB_DEPLOY_WORKFLOW", "deploy.yml").strip() or "deploy.yml"
    ref = os.getenv("GITHUB_DEPLOY_REF", "main").strip() or "main"

    if not repo or not token:
        raise RuntimeError(
            "Missing GITHUB_REPOSITORY or GITHUB_TOKEN in backend environment. "
            "Set both to enable cloud dispatch."
        )

    environment = "production" if target == "production" else "staging"
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
    body = {
        "ref": ref,
        "inputs": {
            "environment": environment,
            "require_smoke": "true",
            "workload_id": workload_id,
        },
    }

    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "compute-allocator-deployer",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:  # nosec B310
            status_code = int(getattr(response, "status", 0) or response.getcode())
    except HTTPError as exc:  # pragma: no cover
        details = ""
        try:
            details = exc.read().decode("utf-8")
        except Exception:
            details = str(exc)
        raise RuntimeError(f"GitHub dispatch failed ({exc.code}): {details}") from exc
    except URLError as exc:  # pragma: no cover
        raise RuntimeError(f"GitHub dispatch network error: {exc}") from exc

    if status_code != 204:
        raise RuntimeError(f"GitHub dispatch returned unexpected status code {status_code}.")

    return {
        "workflow_url": f"https://github.com/{repo}/actions/workflows/{workflow}",
        "run_url": f"https://github.com/{repo}/actions/workflows/{workflow}",
        "workflow": workflow,
        "ref": ref,
        "environment": environment,
    }


def _parse_workload_yaml(yaml_spec: str) -> WorkloadRequestBody:
    try:
        parsed = yaml.safe_load(yaml_spec)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid YAML payload: {exc}") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="YAML payload must be a mapping/object.")

    candidate = parsed.get("workload") if isinstance(parsed.get("workload"), dict) else parsed
    try:
        return WorkloadRequestBody.model_validate(candidate)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


def _parse_competition_yaml(yaml_spec: str) -> CompetitionRequest:
    try:
        parsed = yaml.safe_load(yaml_spec)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid YAML payload: {exc}") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="YAML payload must be a mapping/object.")

    try:
        return CompetitionRequest.model_validate(parsed)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


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
        submitted_at=str(record.get("submitted_at") or _utc_now_iso()),
        status=WorkloadStatus(str(record.get("status") or WorkloadStatus.PENDING.value)),
    )


def run_allocation_pipeline(workload_id: str, node_pool: list[NodeMetrics] | None = None) -> dict:
    workload_record = get_workload(workload_id)
    if workload_record is None:
        raise RuntimeError(f"Workload {workload_id} does not exist.")

    workload = _workload_from_record(workload_record)

    try:
        update_workload_status(workload_id, WorkloadStatus.EVALUATING.value)
        insert_log(workload_id, "Allocation pipeline started.", "info")

        nodes = list(node_pool) if node_pool is not None else collect_node_metrics()
        insert_log(workload_id, f"Collected metrics for {len(nodes)} nodes.", "info")

        scenarios = generate_scenarios(workload, nodes)
        _emit(
            WebSocketEventType.SCENARIO_GENERATED,
            workload_id,
            {"scenarios": scenarios},
        )

        decision = NegotiationEngine().evaluate(scenarios, workload)
        for score in decision.agent_scores:
            _emit(
                WebSocketEventType.AGENT_SCORED,
                workload_id,
                {
                    "agent": score.agent_name.value,
                    "scenario_id": score.scenario_id,
                    "score": score.raw_score,
                    "reasoning": score.reasoning,
                },
            )

        _emit(
            WebSocketEventType.DECISION_MADE,
            workload_id,
            {
                "selected_scenario_id": decision.selected_scenario_id,
                "final_scores": decision.final_scores,
            },
        )

        selected_scenario = next(s for s in scenarios if s.scenario_id == decision.selected_scenario_id)
        manager = DeploymentManager()
        _emit(
            WebSocketEventType.DEPLOYMENT_STARTED,
            workload_id,
            {"node": selected_scenario.target_node},
        )

        manager.create_deployment(workload, selected_scenario)
        deadline = time.time() + 120
        final_status = {"phase": "Failed", "pod_name": "", "node": selected_scenario.target_node}

        while time.time() < deadline:
            pod_status = manager.get_pod_status(workload_id)
            phase = pod_status.get("phase", "Unknown")
            pod_name = pod_status.get("pod_name", "")
            node_name = pod_status.get("node") or selected_scenario.target_node

            insert_log(workload_id, f"Pod {pod_name or 'pending'}: {phase}", "info")
            _emit(
                WebSocketEventType.POD_STATUS_UPDATE,
                workload_id,
                {
                    "pod_name": pod_name,
                    "phase": phase,
                    "node": node_name,
                },
            )

            final_status = {"phase": phase, "pod_name": pod_name, "node": node_name}
            if phase in {"Running", "Succeeded", "Failed"}:
                break
            time.sleep(3)

        if final_status["phase"] in {"Running", "Succeeded"}:
            update_workload_status(workload_id, WorkloadStatus.DEPLOYED.value)
            _emit(
                WebSocketEventType.DEPLOYMENT_SUCCESS,
                workload_id,
                {"pod_name": final_status["pod_name"], "node": final_status["node"]},
            )
            return {
                "status": WorkloadStatus.DEPLOYED.value,
                "node": selected_scenario.target_node,
                "score": decision.final_scores.get(decision.selected_scenario_id, 0.0),
                "selected_scenario_id": decision.selected_scenario_id,
            }

        update_workload_status(workload_id, WorkloadStatus.FAILED.value)
        _emit(
            WebSocketEventType.DEPLOYMENT_FAILED,
            workload_id,
            {"error": f"Deployment ended with phase {final_status['phase']}"},
        )
        return {
            "status": WorkloadStatus.FAILED.value,
            "node": selected_scenario.target_node,
            "score": decision.final_scores.get(decision.selected_scenario_id, 0.0),
            "reason": f"Deployment ended with phase {final_status['phase']}",
        }

    except NoViableNodeError as exc:
        update_workload_status(workload_id, WorkloadStatus.DELAYED.value)
        insert_log(workload_id, str(exc), "warn")
        _emit(WebSocketEventType.DEPLOYMENT_FAILED, workload_id, {"error": str(exc)})
        return {"status": WorkloadStatus.DELAYED.value, "reason": str(exc)}
    except DeploymentError as exc:
        message = str(exc)
        # Local Docker-only mode can evaluate/rank workloads even when a real
        # Kubernetes client is unavailable. Keep the request usable in UI by
        # surfacing it as ready_for_deployment instead of failed.
        if "Unable to initialize Kubernetes client" in message or "config_exception" in message:
            LOGGER.warning("Kubernetes unavailable for workload %s: %s", workload_id, message)
            update_workload_status(workload_id, WorkloadStatus.READY_FOR_DEPLOYMENT.value)
            insert_log(
                workload_id,
                "Kubernetes is unavailable in current environment. Decision generated, deployment skipped.",
                "warn",
            )
            _emit(
                WebSocketEventType.DEPLOYMENT_FAILED,
                workload_id,
                {"error": "Kubernetes unavailable; deployment skipped", "mode": "decision-only"},
            )
            return {
                "status": WorkloadStatus.READY_FOR_DEPLOYMENT.value,
                "reason": "Kubernetes unavailable; deployment skipped (decision-only mode).",
            }

        LOGGER.exception("Deployment error for workload %s", workload_id)
        update_workload_status(workload_id, WorkloadStatus.FAILED.value)
        insert_log(workload_id, f"Deployment failed: {exc}", "error")
        _emit(WebSocketEventType.DEPLOYMENT_FAILED, workload_id, {"error": str(exc)})
        return {"status": WorkloadStatus.FAILED.value, "reason": str(exc)}


def _resolve_selected_scenario(decision: dict) -> DeploymentScenario:
    selected_id = decision.get("selected_scenario_id")
    scenarios = decision.get("all_scenarios") or []
    selected = next((scenario for scenario in scenarios if scenario.get("scenario_id") == selected_id), None)
    if selected is None:
        raise RuntimeError("Selected scenario is missing from decision payload.")
    return DeploymentScenario(
        scenario_id=str(selected["scenario_id"]),
        workload_id=str(selected["workload_id"]),
        target_node=str(selected["target_node"]),
        predicted_latency_ms=float(selected.get("predicted_latency_ms") or 0.0),
        predicted_failure_prob=float(selected.get("predicted_failure_prob") or 0.0),
        estimated_cost_usd=float(selected.get("estimated_cost_usd") or 0.0),
        estimated_energy_kwh=float(selected.get("estimated_energy_kwh") or 0.0),
    )


def _deploy_selected_workload(workload_id: str, target: str) -> None:
    try:
        _set_deployment_state(
            workload_id,
            state="starting",
            target=target,
            mode="local",
            message="Preparing local Kubernetes deployment.",
            new_run=True,
        )
        workload_record = get_workload(workload_id)
        if workload_record is None:
            raise RuntimeError("Workload no longer exists.")

        decision = get_decision(workload_id)
        if decision is None:
            raise RuntimeError("Decision not found for workload.")

        workload = _workload_from_record(workload_record)
        selected_scenario = _resolve_selected_scenario(decision)

        update_workload_status(workload_id, WorkloadStatus.DEPLOYING.value)
        insert_log(workload_id, f"Deployment triggered from API (target={target}).", "info")
        _emit(
            WebSocketEventType.DEPLOYMENT_STARTED,
            workload_id,
            {"node": selected_scenario.target_node, "target": target},
        )
        _set_deployment_state(
            workload_id,
            state="deploying",
            target=target,
            mode="local",
            message=f"Deploying workload to node {selected_scenario.target_node}.",
        )

        manager = DeploymentManager()
        manager.create_deployment(workload, selected_scenario)

        deadline = time.time() + 120
        final_status = {"phase": "Failed", "pod_name": "", "node": selected_scenario.target_node}
        while time.time() < deadline:
            pod_status = manager.get_pod_status(workload_id)
            phase = pod_status.get("phase", "Unknown")
            pod_name = pod_status.get("pod_name", "")
            node_name = pod_status.get("node") or selected_scenario.target_node

            insert_log(workload_id, f"Manual deploy pod {pod_name or 'pending'}: {phase}", "info")
            _emit(
                WebSocketEventType.POD_STATUS_UPDATE,
                workload_id,
                {"pod_name": pod_name, "phase": phase, "node": node_name},
            )

            final_status = {"phase": phase, "pod_name": pod_name, "node": node_name}
            if phase in {"Running", "Succeeded", "Failed"}:
                break
            time.sleep(3)

        if final_status["phase"] in {"Running", "Succeeded"}:
            update_workload_status(workload_id, WorkloadStatus.DEPLOYED.value)
            _emit(
                WebSocketEventType.DEPLOYMENT_SUCCESS,
                workload_id,
                {"pod_name": final_status["pod_name"], "node": final_status["node"]},
            )
            _set_deployment_state(
                workload_id,
                state="deployed",
                target=target,
                mode="local",
                message=f"Deployment succeeded on {final_status['node']}.",
            )
            return

        update_workload_status(workload_id, WorkloadStatus.FAILED.value)
        _emit(
            WebSocketEventType.DEPLOYMENT_FAILED,
            workload_id,
            {"error": f"Deployment ended with phase {final_status['phase']}"},
        )
        insert_log(workload_id, f"Manual deployment failed with phase {final_status['phase']}", "error")
        _set_deployment_state(
            workload_id,
            state="failed",
            target=target,
            mode="local",
            message=f"Deployment ended with phase {final_status['phase']}.",
        )
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Manual deployment failed for workload %s", workload_id)
        update_workload_status(workload_id, WorkloadStatus.READY_FOR_DEPLOYMENT.value)
        insert_log(workload_id, f"Deployment trigger failed: {exc}", "warn")
        _emit(WebSocketEventType.DEPLOYMENT_FAILED, workload_id, {"error": str(exc)})
        _set_deployment_state(
            workload_id,
            state="failed",
            target=target,
            mode="local",
            message=str(exc),
        )


@router.post("/workloads", response_model=WorkloadCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_workload(payload: WorkloadRequestBody, background_tasks: BackgroundTasks) -> WorkloadCreateResponse:
    try:
        workload = _to_workload_request(payload)
        insert_workload(workload)
        insert_log(workload.workload_id, "Workload submitted.", "info")
        background_tasks.add_task(run_allocation_pipeline, workload.workload_id)
        return WorkloadCreateResponse(workload_id=workload.workload_id, status=workload.status)
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Failed to create workload")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workload store is unavailable. Verify Supabase URL/key and project status, then retry.",
        ) from exc


@router.post("/workloads/yaml", response_model=WorkloadCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_workload_from_yaml(payload: WorkloadYamlRequest, background_tasks: BackgroundTasks) -> WorkloadCreateResponse:
    workload_body = _parse_workload_yaml(payload.yaml_spec)
    return create_workload(workload_body, background_tasks)


@router.post("/simulate/competition")
def simulate_competition(request: CompetitionRequest) -> dict:
    workload_a = _to_workload_request(request.workload_a)
    workload_b = _to_workload_request(request.workload_b)

    try:
        insert_workload(workload_a)
        insert_workload(workload_b)
        insert_log(workload_a.workload_id, "Competition simulation workload submitted.", "info")
        insert_log(workload_b.workload_id, "Competition simulation workload submitted.", "info")
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Failed to create competition workloads")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workload store is unavailable. Verify Supabase URL/key and project status, then retry.",
        ) from exc

    ordered = sorted(
        [("workload_a", workload_a), ("workload_b", workload_b)],
        key=lambda item: item[1].priority,
        reverse=True,
    )
    first_label, first_workload = ordered[0]
    second_label, second_workload = ordered[1]

    first_result = run_allocation_pipeline(first_workload.workload_id)
    all_nodes = collect_node_metrics()

    excluded_node = first_result.get("node")
    remaining_nodes = [node for node in all_nodes if node.node_name != excluded_node]

    if not remaining_nodes:
        reason = "No node remains after allocating higher-priority workload."
        update_workload_status(second_workload.workload_id, WorkloadStatus.DELAYED.value)
        insert_log(second_workload.workload_id, reason, "warn")
        second_result = {"status": WorkloadStatus.DELAYED.value, "reason": reason}
    else:
        second_result = run_allocation_pipeline(second_workload.workload_id, node_pool=remaining_nodes)

    allocation_summary = {
        first_label: first_result,
        second_label: second_result,
    }

    return {
        "workload_a_id": workload_a.workload_id,
        "workload_b_id": workload_b.workload_id,
        "allocation_summary": {
            "workload_a": allocation_summary["workload_a"],
            "workload_b": allocation_summary["workload_b"],
        },
    }


@router.post("/simulate/competition/yaml")
def simulate_competition_from_yaml(payload: CompetitionYamlRequest) -> dict:
    request = _parse_competition_yaml(payload.yaml_spec)
    return simulate_competition(request)


@router.get("/workloads/{workload_id}")
def read_workload(workload_id: str) -> dict:
    try:
        workload = get_workload(workload_id)
        if workload is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found.")

        decision = get_decision(workload_id)
        return {"workload": workload, "decision": decision}
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Failed to read workload %s", workload_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/workloads")
def list_workloads() -> list[dict]:
    try:
        response = (
            get_supabase()
            .table("workloads")
            .select("*")
            .order("submitted_at", desc=True)
            .limit(50)
            .execute()
        )
        return response.data or []
    except Exception as exc:  # pragma: no cover
        # Keep dashboard/workload form stable even when Supabase is unreachable.
        LOGGER.warning("Failed to list workloads, returning empty list: %s", exc)
        return []


class DeployRequestBody(BaseModel):
    target: str = Field(default="local", min_length=1)


class RetryDeployRequestBody(BaseModel):
    target: str | None = None


class CancelDeployRequestBody(BaseModel):
    reason: str | None = None


@router.post("/workloads/{workload_id}/deploy", status_code=status.HTTP_202_ACCEPTED)
def deploy_workload(workload_id: str, payload: DeployRequestBody, background_tasks: BackgroundTasks) -> dict:
    workload = get_workload(workload_id)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found.")

    decision = get_decision(workload_id)
    if decision is None or not decision.get("selected_scenario_id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Decision not available yet. Wait for evaluation to complete.",
        )

    target = payload.target.strip().lower()

    if target in {"staging", "production", "cloud"}:
        cloud_target = "production" if target == "production" else "staging"
        update_workload_status(workload_id, WorkloadStatus.DEPLOYING.value)
        _set_deployment_state(
            workload_id,
            state="queued",
            target=cloud_target,
            mode="cloud",
            message="Queuing cloud deployment dispatch.",
            new_run=True,
        )
        try:
            dispatch = _trigger_github_actions_dispatch(workload_id, cloud_target)
            insert_log(
                workload_id,
                f"Cloud deployment dispatched via GitHub Actions ({dispatch['environment']}).",
                "info",
            )
            _set_deployment_state(
                workload_id,
                state="triggered",
                target=cloud_target,
                mode="cloud",
                message="GitHub Actions workflow dispatched.",
                workflow_url=dispatch.get("workflow_url"),
                run_url=dispatch.get("run_url"),
            )
            return {
                "status": WorkloadStatus.DEPLOYING.value,
                "workload_id": workload_id,
                "target": cloud_target,
                "message": "Cloud deployment workflow triggered.",
                "workflow_url": dispatch.get("workflow_url"),
                "run_url": dispatch.get("run_url"),
            }
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("Cloud deployment dispatch failed for %s: %s", workload_id, exc)
            update_workload_status(workload_id, WorkloadStatus.READY_FOR_DEPLOYMENT.value)
            insert_log(workload_id, f"Cloud deployment trigger failed: {exc}", "warn")
            _set_deployment_state(
                workload_id,
                state="failed",
                target=cloud_target,
                mode="cloud",
                message=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cloud deployment trigger failed: {exc}",
            ) from exc

    _set_deployment_state(
        workload_id,
        state="queued",
        target=target,
        mode="local",
        message="Local deployment task queued.",
        new_run=True,
    )

    background_tasks.add_task(_deploy_selected_workload, workload_id, target)

    return {
        "status": WorkloadStatus.DEPLOYING.value,
        "workload_id": workload_id,
        "target": target,
        "message": "Deployment triggered.",
    }


@router.post("/workloads/{workload_id}/deploy/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_deploy_workload(
    workload_id: str,
    payload: RetryDeployRequestBody,
    background_tasks: BackgroundTasks,
) -> dict:
    workload = get_workload(workload_id)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found.")

    latest = get_latest_deployment_state(workload_id)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No previous deployment run found for retry.",
        )

    latest_state = str(latest.get("state") or "").lower()
    if latest_state not in {"failed", "cancelled"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Retry is allowed only from failed/cancelled state (current: {latest_state or 'unknown'}).",
        )

    target = (payload.target or latest.get("target") or "local").strip().lower()
    insert_log(workload_id, f"Deployment retry requested (target={target}).", "info")
    return deploy_workload(workload_id, DeployRequestBody(target=target), background_tasks)


@router.post("/workloads/{workload_id}/deploy/cancel")
def cancel_deploy_workload(workload_id: str, payload: CancelDeployRequestBody) -> dict:
    workload = get_workload(workload_id)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found.")

    latest = get_latest_deployment_state(workload_id)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No deployment run found to cancel.",
        )

    state_now = str(latest.get("state") or "").lower()
    if state_now == "deployed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Deployment already completed; cannot cancel a deployed run.",
        )

    reason = (payload.reason or "Operator requested cancellation.").strip()
    update_workload_status(workload_id, WorkloadStatus.READY_FOR_DEPLOYMENT.value)
    _set_deployment_state(
        workload_id,
        state="cancelled",
        target=str(latest.get("target") or "local"),
        mode=str(latest.get("mode") or "unknown"),
        message=reason,
    )
    insert_log(workload_id, f"Deployment cancelled: {reason}", "warn")

    return {
        "status": WorkloadStatus.READY_FOR_DEPLOYMENT.value,
        "deploy_state": "cancelled",
        "workload_id": workload_id,
        "message": reason,
    }


@router.get("/workloads/{workload_id}/deploy/status")
def read_deploy_status(workload_id: str) -> dict:
    workload = get_workload(workload_id)
    if workload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workload not found.")

    snapshot = get_latest_deployment_state(workload_id)
    if snapshot is not None:
        return {
            "workload_id": workload_id,
            "state": snapshot.get("state"),
            "target": snapshot.get("target"),
            "mode": snapshot.get("mode"),
            "message": snapshot.get("message"),
            "workflow_url": snapshot.get("workflow_url"),
            "run_url": snapshot.get("run_url"),
            "run_id": snapshot.get("run_id"),
            "updated_at": snapshot.get("updated_at"),
            "workload_status": workload.get("status"),
        }

    snapshot = _DEPLOYMENT_STATE.get(workload_id)
    if snapshot is None:
        return {
            "workload_id": workload_id,
            "state": "idle",
            "target": None,
            "mode": "unknown",
            "message": "No explicit deployment has been triggered yet.",
            "updated_at": _utc_now_iso(),
            "workload_status": workload.get("status"),
        }

    payload = dict(snapshot)
    payload["workload_status"] = workload.get("status")
    return payload


@router.get("/metrics/nodes")
def read_latest_node_metrics() -> list[dict]:
    try:
        return [asdict(metric) for metric in get_latest_metrics()]
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Failed to fetch latest node metrics")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
