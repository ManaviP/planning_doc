"""Deep-learning prediction model for workload behavior.

This module is intentionally lightweight and backward-compatible:
- If a trained checkpoint is unavailable, callers can fall back to formula logic.
- Training uses metrics history windows and synthetic targets derived from
  next-step behavior proxies to stay fully local/offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import torch
from torch import nn

WINDOW = 12
FEATURES = 6  # cpu, mem, gpu, pod_norm, net_proxy, reliability
OUTPUTS = 4   # latency, failure_prob, resource_demand, congestion

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
CHECKPOINT_PATH = ARTIFACT_DIR / "dl_predictor.pt"


@dataclass
class DLPrediction:
    predicted_latency_ms: float
    predicted_failure_probability: float
    predicted_resource_demand: float
    predicted_congestion: float


class WorkloadLSTM(nn.Module):
    def __init__(self, input_size: int = FEATURES, hidden_size: int = 48, num_layers: int = 1) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size + 4, 64),
            nn.ReLU(),
            nn.Linear(64, OUTPUTS),
        )

    def forward(self, sequence: torch.Tensor, workload_features: torch.Tensor) -> torch.Tensor:
        _, (hidden, _) = self.lstm(sequence)
        hidden_last = hidden[-1]
        merged = torch.cat([hidden_last, workload_features], dim=1)
        return self.head(merged)


_MODEL_CACHE: WorkloadLSTM | None = None


def _ensure_artifact_dir() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def _to_feature_row(row: dict) -> list[float]:
    cpu = float(row.get("cpu_usage_pct", 0.0)) / 100.0
    mem = float(row.get("memory_usage_pct", 0.0)) / 100.0
    gpu = float(row.get("gpu_usage_pct", 0.0) or 0.0) / 100.0
    pod_norm = min(float(row.get("pod_count", 0.0)) / 30.0, 1.0)
    # network-latency proxy from pressure + contention
    net_proxy = min((cpu + mem) * 0.4 + pod_norm * 0.6, 1.0)
    reliability = 1.0 if bool(row.get("available", True)) else 0.0
    return [cpu, mem, gpu, pod_norm, net_proxy, reliability]


def _build_targets(curr: list[float], nxt: list[float]) -> list[float]:
    cpu, mem, _gpu, pod, net, reliability = curr
    next_cpu, next_mem, _next_gpu, next_pod, _next_net, _next_rel = nxt

    # Proxy targets for supervised training.
    congestion = min((next_cpu + next_mem) / 2.0 * 100.0 + next_pod * 20.0, 100.0)
    latency = 8.0 + congestion * 0.9 + net * 40.0
    failure = min(max((1.0 - reliability) * 0.4 + (congestion / 100.0) * 0.5, 0.01), 0.95)
    demand = min((next_cpu + next_mem) / 2.0 * 1.2 + next_pod * 0.2, 1.5)
    return [latency, failure, demand, congestion]


def build_training_dataset(metrics_rows: list[dict], window: int = WINDOW) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if len(metrics_rows) < window + 2:
        raise ValueError("Insufficient metrics rows for training dataset.")

    seqs: list[list[list[float]]] = []
    work: list[list[float]] = []
    labels: list[list[float]] = []

    by_node: dict[str, list[dict]] = {}
    for row in metrics_rows:
        by_node.setdefault(str(row.get("node_name", "unknown")), []).append(row)

    for rows in by_node.values():
        ordered = sorted(rows, key=lambda item: str(item.get("collected_at", "")))
        feats = [_to_feature_row(item) for item in ordered]
        for i in range(window, len(feats) - 1):
            history = feats[i - window : i]
            current = feats[i]
            nxt = feats[i + 1]
            target = _build_targets(current, nxt)
            seqs.append(history)
            # lightweight workload context proxy from current row
            work.append([current[0], current[1], current[2], current[3]])
            labels.append(target)

    if not seqs:
        raise ValueError("No node windows available for training.")

    return (
        torch.tensor(seqs, dtype=torch.float32),
        torch.tensor(work, dtype=torch.float32),
        torch.tensor(labels, dtype=torch.float32),
    )


def train_model(metrics_rows: list[dict], epochs: int = 12, learning_rate: float = 1e-3) -> dict[str, float]:
    x_seq, x_work, y = build_training_dataset(metrics_rows)
    model = WorkloadLSTM()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_fn = nn.MSELoss()

    model.train()
    for _ in range(max(epochs, 1)):
        optimizer.zero_grad()
        pred = model(x_seq, x_work)
        loss = loss_fn(pred, y)
        loss.backward()
        optimizer.step()

    _ensure_artifact_dir()
    torch.save({"state_dict": model.state_dict()}, CHECKPOINT_PATH)

    global _MODEL_CACHE
    _MODEL_CACHE = model.eval()

    with torch.no_grad():
        final_loss = float(loss_fn(model(x_seq, x_work), y).item())
    return {"samples": float(len(x_seq)), "final_loss": final_loss}


def load_trained_model(force_reload: bool = False) -> WorkloadLSTM | None:
    global _MODEL_CACHE
    if _MODEL_CACHE is not None and not force_reload:
        return _MODEL_CACHE

    if not CHECKPOINT_PATH.exists():
        return None

    try:
        checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu")
        model = WorkloadLSTM()
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        _MODEL_CACHE = model
        return model
    except Exception:
        return None


def infer(
    history_window: Iterable[dict],
    workload_features: dict,
    model: WorkloadLSTM | None = None,
) -> DLPrediction | None:
    rows = list(history_window)
    if len(rows) < WINDOW:
        return None

    model = model or load_trained_model()
    if model is None:
        return None

    sequence_rows = rows[-WINDOW:]
    sequence = torch.tensor([[_to_feature_row(r) for r in sequence_rows]], dtype=torch.float32)

    w = torch.tensor(
        [[
            float(workload_features.get("cpu_cores", 0.0)),
            float(workload_features.get("memory_gb", 0.0)),
            float(workload_features.get("gpu_units", 0.0) or 0.0),
            float(workload_features.get("priority", 1.0)),
        ]],
        dtype=torch.float32,
    )

    with torch.no_grad():
        out = model(sequence, w)[0].tolist()

    latency = max(float(out[0]), 1.0)
    failure = min(max(float(out[1]), 0.0), 0.99)
    demand = min(max(float(out[2]), 0.0), 2.0)
    congestion = min(max(float(out[3]), 0.0), 100.0)

    return DLPrediction(
        predicted_latency_ms=latency,
        predicted_failure_probability=failure,
        predicted_resource_demand=demand,
        predicted_congestion=congestion,
    )
