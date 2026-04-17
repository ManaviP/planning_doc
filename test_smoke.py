"""Smoke test for workload submission and end-to-end persistence checks."""

from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / "backend" / ".env")

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def submit_sample_workload() -> str:
    payload = {
        "name": "smoke-workload",
        "container_image": "sample-workload:latest",
        "cpu_cores": 1.0,
        "gpu_units": None,
        "memory_gb": 1.0,
        "latency_sla_ms": 800,
        "failure_prob_sla": 0.2,
        "risk_tolerance": "medium",
        "budget_usd": 2.0,
        "energy_preference": "any",
        "priority": 3,
    }
    response = requests.post(f"{API_BASE}/workloads", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["workload_id"]


def poll_workload(workload_id: str, timeout_seconds: int = 240) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = requests.get(f"{API_BASE}/workloads/{workload_id}", timeout=30)
        response.raise_for_status()
        data = response.json()
        status = data.get("workload", {}).get("status", "pending")
        print(f"Workload {workload_id} status: {status}")
        if status != "pending":
            return data
        time.sleep(3)
    raise TimeoutError(f"Workload {workload_id} did not leave pending state within timeout")


def assert_decision_exists(workload_id: str) -> dict:
    response = (
        supabase.table("decision_results")
        .select("*")
        .eq("workload_id", workload_id)
        .single()
        .execute()
    )
    if not response.data:
        raise AssertionError("DecisionResult row not found in decision_results")
    return response.data


def print_recent_logs(workload_id: str) -> None:
    rows = (
        supabase.table("log_entries")
        .select("*")
        .eq("workload_id", workload_id)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )
    print("\nLast 5 log entries:")
    for row in rows:
        print(f"- [{row['created_at']}] {row['level'].upper()}: {row['message']}")


def main() -> None:
    workload_id = submit_sample_workload()
    print(f"Submitted workload: {workload_id}")

    workload_payload = poll_workload(workload_id)
    decision = assert_decision_exists(workload_id)
    print_recent_logs(workload_id)

    selected_scenario_id = decision.get("selected_scenario_id")
    final_scores = decision.get("final_scores", {})
    selected_score = final_scores.get(selected_scenario_id)

    scenarios = workload_payload.get("decision", {}).get("all_scenarios", []) or []
    selected_node = None
    for scenario in scenarios:
        if scenario.get("scenario_id") == selected_scenario_id:
            selected_node = scenario.get("target_node")
            break

    print("\nDecision summary:")
    print(f"Selected scenario: {selected_scenario_id}")
    print(f"Selected node: {selected_node}")
    print(f"Selected score: {selected_score}")
    print(f"All final scores: {final_scores}")


if __name__ == "__main__":
    main()
