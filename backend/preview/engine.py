from __future__ import annotations

from dataclasses import asdict

from backend.policy.engine import PolicyGuardrails, evaluate_policy
from backend.pricing.free_pricing import PriceOffer, get_free_cross_cloud_offers


def _estimate_latency_ms(offer: PriceOffer, cpu_cores: float, memory_gb: float) -> float:
    base = {"aws": 115.0, "azure": 112.0, "gcp": 118.0}.get(offer.cloud, 120.0)
    pressure = (cpu_cores * 2.2) + (memory_gb * 0.7)
    return round(base + pressure, 2)


def _estimate_failure_probability(offer: PriceOffer, priority: int) -> float:
    base = {"aws": 0.08, "azure": 0.07, "gcp": 0.09}.get(offer.cloud, 0.1)
    penalty = max(0.0, (3 - float(priority)) * 0.01)
    return round(min(0.25, base + penalty), 4)


def _estimate_energy_kwh(cpu_cores: float, memory_gb: float) -> float:
    return round((cpu_cores * 0.35) + (memory_gb * 0.05), 4)


def _score(option: dict, weights: dict[str, float]) -> float:
    # lower is better for all metrics
    cost = float(option["cost_monthly_usd"])
    risk = float(option["failure_probability"]) * 1000
    latency = float(option["latency_ms"])
    energy = float(option["energy_kwh"])

    # inverse utility to higher-is-better score
    total_cost = (
        weights.get("cost", 0.3) * cost
        + weights.get("risk", 0.35) * risk
        + weights.get("latency", 0.25) * latency
        + weights.get("energy", 0.1) * energy
    )
    return round(max(0.0, 1000.0 / max(total_cost, 1.0)), 4)


def build_preview(payload: dict) -> dict:
    cpu_cores = float(payload.get("cpu_cores", 1.0))
    memory_gb = float(payload.get("memory_gb", 1.0))
    priority = int(payload.get("priority", 3))

    weights = payload.get("weights") or {
        "cost": 0.3,
        "risk": 0.35,
        "latency": 0.25,
        "energy": 0.1,
    }

    policy_payload = payload.get("policy") or {}
    policy = PolicyGuardrails(
        max_monthly_budget_usd=policy_payload.get("max_monthly_budget_usd"),
        max_failure_probability=policy_payload.get("max_failure_probability"),
        max_latency_ms=policy_payload.get("max_latency_ms"),
        allowed_clouds=policy_payload.get("allowed_clouds"),
        allowed_regions=policy_payload.get("allowed_regions"),
    )

    options: list[dict] = []
    for offer in get_free_cross_cloud_offers():
        monthly = round(offer.price_hour_usd * 24 * 30, 4)
        option = {
            "cloud": offer.cloud,
            "region": offer.region,
            "instance_type": offer.instance_type,
            "cost_hour_usd": round(offer.price_hour_usd, 6),
            "cost_monthly_usd": monthly,
            "latency_ms": _estimate_latency_ms(offer, cpu_cores, memory_gb),
            "failure_probability": _estimate_failure_probability(offer, priority),
            "energy_kwh": _estimate_energy_kwh(cpu_cores, memory_gb),
            "price_source": offer.source,
            "price_fetched_at_epoch": offer.fetched_at,
            "confidence": {
                "latency_ms_ci90": [
                    round(_estimate_latency_ms(offer, cpu_cores, memory_gb) - 12.0, 2),
                    round(_estimate_latency_ms(offer, cpu_cores, memory_gb) + 12.0, 2),
                ],
                "failure_probability_ci85": [
                    round(max(0.0, _estimate_failure_probability(offer, priority) - 0.02), 4),
                    round(min(1.0, _estimate_failure_probability(offer, priority) + 0.02), 4),
                ],
            },
        }

        allowed, violations = evaluate_policy(option, policy)
        option["allowed"] = allowed
        option["policy_violations"] = violations
        option["score"] = _score(option, weights) if allowed else 0.0
        options.append(option)

    allowed_options = [o for o in options if o["allowed"]]
    ranked = sorted(allowed_options, key=lambda row: row["score"], reverse=True)
    winner = ranked[0] if ranked else None

    explanation = (
        f"Selected {winner['cloud']} {winner['instance_type']} in {winner['region']} "
        f"with score {winner['score']}."
        if winner
        else "No option satisfies current guardrails. Relax policy constraints."
    )

    return {
        "summary": {
            "candidate_count": len(options),
            "allowed_count": len(allowed_options),
            "blocked_count": len(options) - len(allowed_options),
        },
        "winner": winner,
        "ranked_options": ranked,
        "all_options": options,
        "weights": weights,
        "policy": asdict(policy),
        "explanation": explanation,
    }


def render_templates(run_id: str, preview_result: dict, workload_name: str) -> dict[str, str]:
    winner = preview_result.get("winner") or {}
    instance = winner.get("instance_type", "n/a")
    region = winner.get("region", "n/a")
    cloud = winner.get("cloud", "n/a")

    k8s = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {workload_name}
  labels:
    app: {workload_name}
    preview_run_id: {run_id}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {workload_name}
  template:
    metadata:
      labels:
        app: {workload_name}
    spec:
      containers:
      - name: {workload_name}
        image: nginx:stable
        resources:
          limits:
            cpu: \"1\"
            memory: \"1Gi\"
"""

    tf = f"""terraform {{
  required_version = \">= 1.5.0\"
}}

# Preview suggestion
# cloud={cloud} region={region} instance_type={instance}
"""

    cicd = f"""name: deploy-preview
on:
  workflow_dispatch:
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo \"Deploying {workload_name} with preview run {run_id}\"
"""

    return {
        "deployment.yaml": k8s,
        "main.tf": tf,
        "deploy.yml": cicd,
    }
