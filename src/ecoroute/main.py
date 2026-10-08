from fastapi import FastAPI
from pydantic import BaseModel

from ecoroute.config import Settings


class HealthResponse(BaseModel):
    status: str
    profile: str
    phase: str
    integrations_enabled: bool


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="EcoRoute AI", version="0.0.1",
        description="Phase 0 scaffold. Routing, observations and ML are not yet implemented.",
        docs_url=None, redoc_url=None,
    )

    @app.get("/healthz", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", profile=settings.ecoroute_profile,
                              phase="0-scaffold", integrations_enabled=False)

    return app


app = create_app()
