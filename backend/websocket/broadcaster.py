"""WebSocket event broadcasting for workload orchestration updates."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.db import insert_log
from backend.models import WebSocketEvent, WebSocketEventType

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, workload_id: str) -> None:
        await ws.accept()
        async with self._lock:
            self.active_connections[workload_id].add(ws)

    async def disconnect(self, ws: WebSocket, workload_id: str) -> None:
        async with self._lock:
            connections = self.active_connections.get(workload_id)
            if not connections:
                return
            connections.discard(ws)
            if not connections:
                self.active_connections.pop(workload_id, None)

    async def broadcast(self, event: WebSocketEvent) -> None:
        if event.event_type == WebSocketEventType.LOG_LINE:
            insert_log(
                event.workload_id,
                str(event.payload.get("message", "")),
                str(event.payload.get("level", "info")),
            )

        payload = _serialize_event(event)
        async with self._lock:
            recipients = list(self.active_connections.get(event.workload_id, set()))

        stale_connections: list[WebSocket] = []
        for ws in recipients:
            try:
                await ws.send_json(payload)
            except Exception:
                stale_connections.append(ws)

        for ws in stale_connections:
            await self.disconnect(ws, event.workload_id)


manager = ConnectionManager()


def _serialize_value(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _serialize_value(val) for key, val in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _serialize_value(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _serialize_event(event: WebSocketEvent) -> dict[str, Any]:
    return {
        "event_type": event.event_type.value,
        "workload_id": event.workload_id,
        "payload": _serialize_value(event.payload),
        "timestamp": event.timestamp or datetime.now(timezone.utc).isoformat(),
    }


async def emit_event(event: WebSocketEvent) -> None:
    await manager.broadcast(event)


def emit_event_sync(event: WebSocketEvent) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(emit_event(event))
        return

    loop.create_task(emit_event(event))


@router.websocket("/ws/{workload_id}")
async def workload_ws(websocket: WebSocket, workload_id: str) -> None:
    await manager.connect(websocket, workload_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket, workload_id)
    except Exception:
        await manager.disconnect(websocket, workload_id)
