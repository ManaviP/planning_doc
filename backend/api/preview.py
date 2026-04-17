from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.preview.engine import build_preview, render_templates

router = APIRouter(prefix="/preview", tags=["preview"])

_RUNS: dict[str, dict] = {}


class PreviewPolicy(BaseModel):
    max_monthly_budget_usd: float | None = Field(default=None, ge=0)
    max_failure_probability: float | None = Field(default=None, ge=0, le=1)
    max_latency_ms: float | None = Field(default=None, ge=1)
    allowed_clouds: list[str] | None = None
    allowed_regions: list[str] | None = None


class PreviewWeights(BaseModel):
    cost: float = Field(default=0.3, ge=0)
    risk: float = Field(default=0.35, ge=0)
    latency: float = Field(default=0.25, ge=0)
    energy: float = Field(default=0.1, ge=0)


class PreviewRequest(BaseModel):
    name: str = Field(min_length=1)
    cpu_cores: float = Field(gt=0)
    memory_gb: float = Field(gt=0)
    priority: int = Field(default=3, ge=1, le=5)
    policy: PreviewPolicy | None = None
    weights: PreviewWeights | None = None


@router.post("/run")
def run_preview(request: PreviewRequest) -> dict:
    run_id = str(uuid4())
    payload = request.model_dump()
    result = build_preview(payload)
    _RUNS[run_id] = {
        "run_id": run_id,
        "request": payload,
        "result": result,
    }
    return _RUNS[run_id]


@router.get("/{run_id}")
def read_preview(run_id: str) -> dict:
    run = _RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Preview run not found")
    return run


@router.get("/{run_id}/export")
def export_preview_templates(run_id: str) -> StreamingResponse:
    run = _RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Preview run not found")

    files = render_templates(
        run_id=run_id,
        preview_result=run["result"],
        workload_name=str(run["request"].get("name", "workload")).replace(" ", "-").lower(),
    )
    archive = BytesIO()
    with ZipFile(archive, mode="w", compression=ZIP_DEFLATED) as zip_handle:
        for name, content in files.items():
            zip_handle.writestr(name, content)

    archive.seek(0)
    filename = f"preview-{run_id}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(archive, media_type="application/zip", headers=headers)
