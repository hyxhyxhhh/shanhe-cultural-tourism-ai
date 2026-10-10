from datetime import datetime, timezone
from typing import Any
import asyncio
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.activity_api import router as activity_router
from backend.annual_activity_api import router as annual_activity_router
from backend.auth import router as auth_router
from backend.db import engine
from backend.model_catalog import router as model_catalog_router
from backend.app.routers.register import register_wenhao_routers

app = FastAPI(title="Shanhe Tourism Decision API", version="0.1.0")
app.include_router(auth_router)
app.include_router(activity_router)
app.include_router(annual_activity_router)
app.include_router(model_catalog_router)
register_wenhao_routers(app)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "shanhe-tourism-decision", "time": datetime.now(timezone.utc).isoformat()}

@app.get("/health/database")
def database_health() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return {"status": "unavailable", "service": "postgresql"}
    return {"status": "ok", "service": "postgresql"}

@app.post("/api/agents/{agent_id}/run")
def run_agent(agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"id": "run-placeholder", "agentId": agent_id, "status": "idle", "input": payload}

@app.get("/api/agents/{agent_id}/runs/{run_id}")
def get_run(agent_id: str, run_id: str) -> dict[str, Any]:
    return {"id": run_id, "agentId": agent_id, "status": "idle", "steps": []}

@app.get("/api/agents/{agent_id}/runs/{run_id}/stream")
def stream_run(agent_id: str, run_id: str) -> StreamingResponse:
    async def events():
        payload = {"type": "message", "agentId": agent_id, "runId": run_id, "message": "SSE endpoint reserved"}
        yield f"event: message\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0)

    return StreamingResponse(events(), media_type="text/event-stream")
