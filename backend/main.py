"""FastAPI application entrypoint for the compute allocator backend."""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.results import router as results_router
from backend.api.preview import router as preview_router
from backend.api.workload import router as workload_router
from backend.api.shadow import router as shadow_router
from backend.learning.trainer import start_retrainer
from backend.metrics.collector import start_metrics_collector
from backend.websocket.broadcaster import router as websocket_router

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="AI-Orchestrated Compute Allocation API",
    version="0.1.0",
    description="Prototype backend for cost-risk-aware Kubernetes workload allocation.",
)

# CORS middleware must be added FIRST before routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

app.include_router(workload_router)
app.include_router(results_router)
app.include_router(preview_router)
app.include_router(shadow_router)
app.include_router(websocket_router)


@app.on_event("startup")
def on_startup() -> None:
    load_dotenv(BASE_DIR / ".env")
    load_dotenv(BASE_DIR.parent / ".env", override=False)
    start_metrics_collector()
    # Starts a daemon thread; safe even if training data is not yet available.
    start_retrainer()
    LOGGER.info("Backend startup complete.")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
