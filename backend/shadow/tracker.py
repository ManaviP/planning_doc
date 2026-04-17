from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


@dataclass
class ShadowRecord:
    shadow_id: str
    run_id: str
    predicted_cost_monthly_usd: float
    predicted_latency_ms: float
    predicted_failure_probability: float
    actual_cost_monthly_usd: float | None = None
    actual_latency_ms: float | None = None
    actual_failure_probability: float | None = None


_SHADOWS: dict[str, ShadowRecord] = {}


def register_shadow(
    run_id: str,
    predicted_cost_monthly_usd: float,
    predicted_latency_ms: float,
    predicted_failure_probability: float,
) -> ShadowRecord:
    record = ShadowRecord(
        shadow_id=str(uuid4()),
        run_id=run_id,
        predicted_cost_monthly_usd=predicted_cost_monthly_usd,
        predicted_latency_ms=predicted_latency_ms,
        predicted_failure_probability=predicted_failure_probability,
    )
    _SHADOWS[record.shadow_id] = record
    return record


def attach_actuals(
    shadow_id: str,
    actual_cost_monthly_usd: float,
    actual_latency_ms: float,
    actual_failure_probability: float,
) -> ShadowRecord | None:
    record = _SHADOWS.get(shadow_id)
    if record is None:
        return None
    record.actual_cost_monthly_usd = actual_cost_monthly_usd
    record.actual_latency_ms = actual_latency_ms
    record.actual_failure_probability = actual_failure_probability
    return record


def read_shadow(shadow_id: str) -> ShadowRecord | None:
    return _SHADOWS.get(shadow_id)


def trust_summary() -> dict:
    rows = list(_SHADOWS.values())
    compared = [
        r
        for r in rows
        if r.actual_cost_monthly_usd is not None
        and r.actual_latency_ms is not None
        and r.actual_failure_probability is not None
    ]

    if not compared:
        return {
            "registered": len(rows),
            "compared": 0,
            "trust_score": None,
            "notes": "No actual outcomes attached yet.",
        }

    def _acc(pred: float, actual: float, floor: float = 1.0) -> float:
        return max(0.0, 1.0 - abs(actual - pred) / max(abs(pred), floor))

    scores = []
    for row in compared:
        cost_acc = _acc(row.predicted_cost_monthly_usd, float(row.actual_cost_monthly_usd), floor=10.0)
        latency_acc = _acc(row.predicted_latency_ms, float(row.actual_latency_ms), floor=10.0)
        risk_acc = max(0.0, 1.0 - abs(float(row.actual_failure_probability) - row.predicted_failure_probability))
        scores.append((cost_acc + latency_acc + risk_acc) / 3.0)

    trust = sum(scores) / len(scores)
    return {
        "registered": len(rows),
        "compared": len(compared),
        "trust_score": round(trust, 4),
    }
