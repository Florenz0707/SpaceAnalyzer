"""Assemble the local API, worker lifecycle, and built frontend."""

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.middleware.base import RequestResponseEndpoint

from spaceanalyzer.api.snapshots import router
from spaceanalyzer.services.snapshots import ScanBusyError, SnapshotService

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "spaceanalyzer"
    read_only: bool = True


def create_app(database: Path | None = None, static_dir: Path | None = None) -> FastAPI:
    database = database or Path(
        os.environ.get(
            "SPACEANALYZER_DATABASE", str(PROJECT_ROOT / "data/snapshots.sqlite3")
        )
    )
    static_dir = (static_dir or PROJECT_ROOT / "frontend/dist").resolve()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        service = SnapshotService(database)
        application.state.snapshot_service = service
        try:
            yield
        finally:
            await asyncio.to_thread(service.close)

    application = FastAPI(title="SpaceAnalyzer", version="0.1.0", lifespan=lifespan)
    application.include_router(router)

    @application.middleware("http")
    async def local_requests(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            host = urlsplit("http://" + request.headers.get("host", "")).hostname
            if host not in LOCAL_HOSTS:
                return JSONResponse({"detail": "Local Host required"}, status_code=403)
            origin = request.headers.get("origin")
            if origin:
                parsed = urlsplit(origin)
                if (
                    parsed.hostname not in LOCAL_HOSTS
                    or parsed.scheme != "http"
                    or parsed.port
                    not in {
                        None,
                        8000,
                        5173,
                        4173,
                        request.url.port,
                    }
                ):
                    return JSONResponse(
                        {"detail": "Origin is not allowed"}, status_code=403
                    )
        except ValueError:
            return JSONResponse({"detail": "Malformed local request"}, status_code=403)
        return await call_next(request)

    @application.exception_handler(KeyError)
    async def unknown_record(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=404)

    @application.exception_handler(ValueError)
    @application.exception_handler(OSError)
    async def invalid_input(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=400)

    @application.exception_handler(ScanBusyError)
    async def busy(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=409)

    @application.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @application.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            return JSONResponse({"detail": "Unknown API route"}, status_code=404)
        candidate = (static_dir / path).resolve()
        if not candidate.is_relative_to(static_dir):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        if candidate.is_file():
            return FileResponse(candidate)
        index = static_dir / "index.html"
        if index.is_file() and not Path(path).suffix:
            return FileResponse(index)
        return JSONResponse(
            {"detail": "Frontend asset not found; build frontend first"},
            status_code=404,
        )

    return application


app = create_app()
