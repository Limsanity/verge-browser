from fastapi import FastAPI

from app.config import get_settings
from app.routes.browser import router as browser_router
from app.routes.files import router as files_router
from app.routes.health import router as health_router
from app.routes.sandboxes import router as sandbox_router
from app.routes.shell import router as shell_router
from app.routes.vnc import router as vnc_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.include_router(health_router)
    app.include_router(sandbox_router)
    app.include_router(browser_router)
    app.include_router(vnc_router)
    app.include_router(shell_router)
    app.include_router(files_router)
    return app


app = create_app()

