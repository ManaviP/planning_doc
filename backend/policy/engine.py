from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PolicyGuardrails:
    max_monthly_budget_usd: float | None = None
    max_failure_probability: float | None = None
    max_latency_ms: float | None = None
    allowed_clouds: list[str] | None = None
    allowed_regions: list[str] | None = None


def evaluate_policy(option: dict, policy: PolicyGuardrails) -> tuple[bool, list[str]]:
    violations: list[str] = []

    if policy.max_monthly_budget_usd is not None:
        if float(option.get("cost_monthly_usd", 0.0)) > policy.max_monthly_budget_usd:
            violations.append("budget_exceeded")

    if policy.max_failure_probability is not None:
        if float(option.get("failure_probability", 0.0)) > policy.max_failure_probability:
            violations.append("risk_exceeded")

    if policy.max_latency_ms is not None:
        if float(option.get("latency_ms", 0.0)) > policy.max_latency_ms:
            violations.append("latency_exceeded")

    if policy.allowed_clouds:
        if str(option.get("cloud", "")).lower() not in {c.lower() for c in policy.allowed_clouds}:
            violations.append("cloud_not_allowed")

    if policy.allowed_regions:
        if str(option.get("region", "")).lower() not in {r.lower() for r in policy.allowed_regions}:
            violations.append("region_not_allowed")

    return (len(violations) == 0, violations)
