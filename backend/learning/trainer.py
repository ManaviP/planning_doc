"""Continuous learning service for periodic DL model retraining."""

from __future__ import annotations

import logging
import threading
import time

from backend.db import get_metrics_history
from backend.prediction.dl_model import train_model

LOGGER = logging.getLogger(__name__)

_RETRAIN_THREAD: threading.Thread | None = None


def _retrain_once() -> None:
    try:
        rows = get_metrics_history(limit=5000)
        if len(rows) < 200:
            LOGGER.info("Skipping retrain: not enough metrics rows (%s).", len(rows))
            return
        metrics = train_model(rows, epochs=8)
        LOGGER.info("DL model retrained: samples=%s, loss=%.5f", int(metrics.get("samples", 0.0)), metrics.get("final_loss", 0.0))
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("DL retraining iteration failed: %s", exc)


def _run_forever(interval_seconds: int) -> None:
    while True:
        _retrain_once()
        time.sleep(max(interval_seconds, 60))


def start_retrainer(interval_seconds: int = 1800) -> None:
    global _RETRAIN_THREAD
    if _RETRAIN_THREAD and _RETRAIN_THREAD.is_alive():
        return

    _RETRAIN_THREAD = threading.Thread(
        target=_run_forever,
        args=(interval_seconds,),
        name="dl-retrainer",
        daemon=True,
    )
    _RETRAIN_THREAD.start()
