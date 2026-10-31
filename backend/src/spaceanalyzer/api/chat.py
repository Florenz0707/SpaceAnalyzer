"""Conversation commands and reconnectable SSE over persisted run events."""

import asyncio
from collections.abc import AsyncIterator
from time import monotonic
from typing import cast

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from spaceanalyzer.analysis.conversations import AnalysisRun, Conversation
from spaceanalyzer.analysis.workflow import AnalysisWorkflow

router = APIRouter(prefix="/api")


def workflow(request: Request) -> AnalysisWorkflow:
    return cast(AnalysisWorkflow, request.app.state.analysis_workflow)


class ConversationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_id: str
    model_key: str
    allow_cloud: bool = False


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    request_key: str = Field(min_length=1, max_length=80)


@router.get("/models")
def models(request: Request) -> dict[str, object]:
    registry = workflow(request).registry
    return {
        "items": [model.model_dump() for model in registry.list_models()],
        "diagnostics": registry.diagnostics,
    }


@router.post("/models/{key}/check")
async def check_model(key: str, request: Request) -> dict[str, bool]:
    return {
        "available": await workflow(request)
        .registry.resolve(key)
        .adapter.check_connection()
    }


@router.post("/conversations", status_code=201)
def create_conversation(body: ConversationInput, request: Request) -> Conversation:
    return workflow(request).create_conversation(
        body.snapshot_id, body.model_key, body.allow_cloud
    )


@router.get("/conversations")
def conversations(snapshot_id: str, request: Request) -> list[Conversation]:
    service = workflow(request)
    service.builder.snapshots.get_snapshot(snapshot_id)
    return service.store.list_conversations(snapshot_id)


@router.get("/conversations/{conversation_id}/runs")
def history(conversation_id: str, request: Request) -> list[AnalysisRun]:
    return workflow(request).store.runs(conversation_id)


@router.post("/conversations/{conversation_id}/runs", status_code=202)
async def start_run(
    conversation_id: str, body: RunInput, request: Request
) -> AnalysisRun:
    return await workflow(request).start_run(
        conversation_id, body.question, body.request_key
    )


@router.get("/runs/{run_id}")
def run(run_id: str, request: Request) -> AnalysisRun:
    return workflow(request).get_run(run_id)


@router.post("/runs/{run_id}/cancel")
async def cancel(run_id: str, request: Request) -> AnalysisRun:
    return await workflow(request).cancel(run_id)


@router.get("/snapshots/{snapshot_id}/nodes/{node_id}")
def node(snapshot_id: str, node_id: int, request: Request) -> dict[str, object]:
    return workflow(request).builder.query(snapshot_id, "node", {"node_id": node_id})


@router.get("/runs/{run_id}/events")
async def events(
    run_id: str, request: Request, after: int = Query(0, ge=0)
) -> StreamingResponse:
    service = workflow(request)
    service.get_run(run_id)
    try:
        cursor = int(request.headers.get("last-event-id", str(after)))
        if cursor < 0:
            raise ValueError()
    except ValueError:
        raise ValueError("Invalid event cursor") from None

    async def stream() -> AsyncIterator[str]:
        current = cursor
        heartbeat = monotonic()
        while True:
            if await request.is_disconnected():
                return
            batch = await asyncio.to_thread(service.events, run_id, current)
            for event in batch:
                yield f"id: {event.sequence}\ndata: {event.model_dump_json()}\n\n"
                current = event.sequence
            state = await asyncio.to_thread(service.get_run, run_id)
            if len(batch) < 100 and state.status not in {"queued", "running"}:
                # Recheck after reading state to retain the terminal event.
                remaining = await asyncio.to_thread(service.events, run_id, current)
                if not remaining:
                    return
                continue
            if monotonic() - heartbeat > 10:
                yield ": keepalive\n\n"
                heartbeat = monotonic()
            await asyncio.sleep(0.15)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
