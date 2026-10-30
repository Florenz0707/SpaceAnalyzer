"""Application entry point; filesystem scanning is added in a later milestone."""

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Stable health contract for local clients."""

    status: str = "ok"
    service: str = "spaceanalyzer"
    read_only: bool = True


def create_app() -> FastAPI:
    """Create the API without scanning disks or creating application data."""
    application = FastAPI(title="SpaceAnalyzer", version="0.1.0")

    @application.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    return application


app = create_app()
