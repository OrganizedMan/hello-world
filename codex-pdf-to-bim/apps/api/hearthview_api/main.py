from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from hearthview.events import ProjectRepository
from hearthview.storage import ArtifactStore

from hearthview_api.config import AppConfig
from hearthview_api.errors import DomainError
from hearthview_api.routes.projects import router as projects_router
from hearthview_api.routes.model import router as model_router
from hearthview_api.routes.render import router as render_router


def create_app(config: AppConfig | None = None) -> FastAPI:
    resolved_config = config or AppConfig.from_environment()
    resolved_config.data_root.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="HearthView Local API", version="0.1.0")
    app.state.config = resolved_config
    app.state.artifact_store = ArtifactStore(resolved_config.data_root / "artifacts")
    app.state.repository = ProjectRepository(resolved_config.data_root / "hearthview.sqlite3")
    app.state.repository.mark_source_profile(
        resolved_config.supported_source_sha256,
        "GARRIGAN_A1",
    )
    app.state.render_jobs = {}

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"code": error.code, "message": error.message, "action": error.action},
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "hearthview-api"}

    app.include_router(projects_router)
    app.include_router(model_router)
    app.include_router(render_router)
    return app


app = create_app()
