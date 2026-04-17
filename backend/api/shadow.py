from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.shadow.tracker import attach_actuals, read_shadow, register_shadow, trust_summary

router = APIRouter(prefix="/shadow", tags=["shadow"])


class ShadowRegisterRequest(BaseModel):
    run_id: str
    predicted_cost_monthly_usd: float = Field(ge=0)
    predicted_latency_ms: float = Field(ge=0)
    predicted_failure_probability: float = Field(ge=0, le=1)


class ShadowActualsRequest(BaseModel):
    actual_cost_monthly_usd: float = Field(ge=0)
    actual_latency_ms: float = Field(ge=0)
    actual_failure_probability: float = Field(ge=0, le=1)


@router.post("/register")
def register_shadow_run(request: ShadowRegisterRequest) -> dict:
    record = register_shadow(
        run_id=request.run_id,
        predicted_cost_monthly_usd=request.predicted_cost_monthly_usd,
        predicted_latency_ms=request.predicted_latency_ms,
        predicted_failure_probability=request.predicted_failure_probability,
    )
    return asdict(record)


@router.post("/{shadow_id}/actuals")
def update_shadow_actuals(shadow_id: str, request: ShadowActualsRequest) -> dict:
    record = attach_actuals(
        shadow_id=shadow_id,
        actual_cost_monthly_usd=request.actual_cost_monthly_usd,
        actual_latency_ms=request.actual_latency_ms,
        actual_failure_probability=request.actual_failure_probability,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Shadow run not found")
    return asdict(record)


@router.get("/{shadow_id}")
def get_shadow_run(shadow_id: str) -> dict:
    record = read_shadow(shadow_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Shadow run not found")
    return asdict(record)


@router.get("/trust/summary")
def get_shadow_trust_summary() -> dict:
    return trust_summary()
